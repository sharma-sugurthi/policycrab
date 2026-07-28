"""
Multi-LLM Router — intelligent model selection with automatic fallback.

Strategy:
- Gemini is the PRIMARY model for ALL task types (XPRIZE compliance).
- On rate limit (429) or error, falls back to secondary providers.
- All calls are logged with structured step logs for the AI Transparency UI.
"""

import asyncio
import inspect
import logging
import time
from enum import Enum
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from app.config import settings

logger = logging.getLogger(__name__)


class LLMRateLimitError(RuntimeError):
    """Raised when every configured LLM provider is currently rate-limited.

    Callers (HTTP routes) should surface this as HTTP 503 with a Retry-After
    header rather than a generic 500, so clients know to back off and retry.
    """


class TaskType(str, Enum):
    """Task types that determine which LLM to use."""
    EXTRACTION = "extraction"          # Policy parsing, structured output
    TOOL_CALLING = "tool_calling"      # Agent tool use, CPT/ICD lookup
    LEGAL_WRITING = "legal_writing"    # Appeal letter drafting (highest quality)
    REASONING = "reasoning"            # Deep contradiction analysis (Policy Analyzer)
    EXPLANATION = "explanation"        # Jargon → plain English
    CHAT = "chat"                      # Interactive Q&A


# ── AI Step Logs — emitted for the AI Transparency UI ────────────
# Each task type emits structured logs consumed by AILogViewer on the frontend.
TASK_STEP_LOGS: dict[TaskType, list[str]] = {
    TaskType.EXTRACTION: [
        "[Gemini] Parsing policy document structure...",
        "[Gemini] Extracting deductible and OOP max values...",
        "[Gemini] Classifying plan type (HMO/PPO/HDHP)...",
        "[Gemini] Detecting legal classification (ERISA/ACA/State)...",
        "[Gemini] Policy profile structured and validated ✓",
    ],
    TaskType.TOOL_CALLING: [
        "[Gemini] Looking up CPT code in billing database...",
        "[Gemini] Cross-referencing ICD-10 diagnosis codes...",
        "[Gemini] Checking network status (In/Out-of-Network)...",
        "[Gemini] Evaluating NSA applicability for this claim...",
        "[Gemini] Tool calls complete ✓",
    ],
    TaskType.LEGAL_WRITING: [
        "[Gemini Pro] Routing claim to appeal framework (ERISA/ACA/NSA)...",
        "[Gemini Pro] Retrieving regulatory knowledge chunks via RAG...",
        "[Gemini Pro] Cross-referencing CARC/RARC denial codes...",
        "[Gemini Pro] Calculating appeal deadline and urgency...",
        "[Gemini Pro] Drafting formal appeal letter with legal citations...",
        "[Gemini Pro] Validating citations against knowledge base ✓",
    ],
    TaskType.REASONING: [
        "[Gemini Pro] Loading patient policy document from vector store...",
        "[Gemini Pro] Generating targeted queries from denial reason...",
        "[Gemini Pro] Retrieving relevant policy clauses by semantic search...",
        "[Gemini Pro] Comparing denial reason to retrieved policy language...",
        "[Gemini Pro] Detecting contradictions and insurer mistakes...",
        "[Gemini Pro] Extracting exact page numbers and clause text ✓",
    ],
    TaskType.EXPLANATION: [
        "[Gemini] Translating insurance jargon to plain English...",
        "[Gemini] Summarizing patient rights and next steps...",
        "[Gemini] Explanation complete ✓",
    ],
    TaskType.CHAT: [
        "[Gemini] Processing question in healthcare context...",
        "[Gemini] Referencing loaded policy profile...",
        "[Gemini] Generating response ✓",
    ],
}


# ── Model Registry ────────────────────────────────────────────────
# XPRIZE Compliance: Gemini is PRIMARY for all task types.
# Other providers are fallbacks for resilience only.

_MODEL_REGISTRY: dict[TaskType, list[dict]] = {
    TaskType.EXTRACTION: [
        {"provider": "gemini", "model": "gemini-2.5-flash"},                             # Primary
        {"provider": "siliconflow", "model": "Qwen/Qwen2.5-72B-Instruct"},               # Fallback 1 (Free Qwen 72B)
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},                        # Fallback 2
    ],
    TaskType.TOOL_CALLING: [
        {"provider": "gemini", "model": "gemini-2.5-flash"},
        {"provider": "siliconflow", "model": "Qwen/Qwen2.5-72B-Instruct"},
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    ],
    TaskType.LEGAL_WRITING: [
        {"provider": "gemini", "model": "gemini-2.5-pro"},                               # Primary
        {"provider": "moonshot", "model": "moonshot-v1-32k"},                            # Fallback 1 (Kimi 32k)
        {"provider": "deepseek", "model": "deepseek-chat"},                              # Fallback 2 (Direct DeepSeek-V3)
    ],
    TaskType.REASONING: [
        {"provider": "deepseek", "model": "deepseek-reasoner"},                          # Primary (DeepSeek-R1 Direct)
        {"provider": "gemini", "model": "gemini-2.5-pro"},                               # Fallback 1
        {"provider": "moonshot", "model": "moonshot-v1-32k"},                            # Fallback 2 (Kimi)
    ],
    TaskType.EXPLANATION: [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},                        # Primary (Fast)
        {"provider": "moonshot", "model": "moonshot-v1-8k"},                             # Fallback 1 (Kimi)
    ],
    TaskType.CHAT: [
        {"provider": "gemini", "model": "gemini-2.5-flash"},
        {"provider": "deepseek", "model": "deepseek-chat"},
        {"provider": "siliconflow", "model": "Qwen/Qwen2.5-72B-Instruct"},
    ],
}


def _create_llm(provider: str, model: str, temperature: float = 0.0) -> BaseChatModel | None:
    """Create a LangChain chat model for the given provider."""
    try:
        if provider == "gemini" and settings.gemini_api_key:
            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=settings.gemini_api_key,
                temperature=temperature,
                convert_system_message_to_human=False,
                max_retries=0,
                timeout=30,
            )
        elif provider == "groq" and settings.groq_api_key:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=model,
                api_key=settings.groq_api_key,
                temperature=temperature,
            )
        elif provider == "openrouter" and settings.openrouter_api_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=temperature,
            )
        elif provider == "deepseek" and settings.deepseek_api_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com",
                temperature=temperature,
            )
        elif provider == "moonshot" and settings.moonshot_api_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=settings.moonshot_api_key,
                base_url="https://api.moonshot.cn/v1",
                temperature=temperature,
            )
        elif provider == "siliconflow" and settings.siliconflow_api_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=settings.siliconflow_api_key,
                base_url="https://api.siliconflow.cn/v1",
                temperature=temperature,
            )
        elif provider == "cerebras" and settings.cerebras_api_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=settings.cerebras_api_key,
                base_url="https://api.cerebras.ai/v1",
                temperature=temperature,
            )
        elif provider == "grok" and settings.grok_api_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=settings.grok_api_key,
                base_url="https://api.x.ai/v1",
                temperature=temperature,
            )
    except Exception as e:
        logger.warning(f"Failed to create {provider}/{model}: {e}")
    return None


class FallbackChatModel:
    """Wrap several candidate chat models and fall back on runtime failures."""

    def __init__(self, task: TaskType, candidates: list[dict], temperature: float = 0.0, max_retries: int = 3):
        self.task = task
        self.candidates = candidates
        self.temperature = temperature
        self.max_retries = max_retries
        self.bound_tools = None
        self._created_llms: dict[tuple[str, str], BaseChatModel] = {}

    def _create_candidate(self, entry: dict) -> BaseChatModel | None:
        key = (entry["provider"], entry["model"])
        if key not in self._created_llms:
            self._created_llms[key] = _create_llm(entry["provider"], entry["model"], self.temperature)
        return self._created_llms[key]

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def _bind_if_needed(self, llm: BaseChatModel) -> BaseChatModel:
        if self.bound_tools is not None and hasattr(llm, "bind_tools"):
            return llm.bind_tools(self.bound_tools)
        return llm

    def _invoke_with_fallback(self, invoke_method, input_data, config=None, **kwargs):
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            for entry in self.candidates:
                llm = self._create_candidate(entry)
                if llm is None:
                    continue

                try:
                    bound_llm = self._bind_if_needed(llm)
                    logger.info(
                        f"LLM selected for {self.task.value} (attempt {attempt + 1}): "
                        f"{entry['provider']}/{entry['model']}"
                    )
                    return invoke_method(bound_llm, input_data, config=config, **kwargs)
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        f"LLM provider {entry['provider']}/{entry['model']} failed for task {self.task.value}: {exc}"
                    )

            if attempt < self.max_retries - 1:
                wait_time = (2 ** attempt) * 2
                logger.warning(
                    f"Retrying LLM providers for task {self.task.value} in {wait_time}s"
                )
                time.sleep(wait_time)

        if last_error is not None:
            # Surface rate-limit exhaustion as a distinct error type so HTTP
            # routes can return 503 / Retry-After instead of a generic 500.
            err_str = str(last_error)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate_limit" in err_str.lower():
                raise LLMRateLimitError(
                    f"All LLM providers are rate-limited for task '{self.task.value}'. "
                    f"Last error: {last_error}"
                ) from last_error
            raise last_error

        raise RuntimeError(
            f"No LLM available for task '{self.task.value}' after {self.max_retries} retries. "
            "Check that at least one API key is configured in .env"
        )

    def invoke(self, input_data, config=None, **kwargs):
        return self._invoke_with_fallback(lambda llm, data, config=None, **call_kwargs: self._call_llm(llm, data, method_name="invoke", config=config, **call_kwargs), input_data, config=config, **kwargs)

    async def ainvoke(self, input_data, config=None, **kwargs):
        return await self._invoke_with_fallback_async(
            lambda llm, data, config=None, **call_kwargs: self._call_llm_async(llm, data, method_name="ainvoke", config=config, **call_kwargs),
            input_data,
            config=config,
            **kwargs,
        )

    async def _invoke_with_fallback_async(self, invoke_method, input_data, config=None, **kwargs):
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            for entry in self.candidates:
                llm = self._create_candidate(entry)
                if llm is None:
                    continue

                try:
                    bound_llm = self._bind_if_needed(llm)
                    logger.info(
                        f"LLM selected for {self.task.value} (attempt {attempt + 1}): "
                        f"{entry['provider']}/{entry['model']}"
                    )
                    return await invoke_method(bound_llm, input_data, config=config, **kwargs)
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        f"LLM provider {entry['provider']}/{entry['model']} failed for task {self.task.value}: {exc}"
                    )

            if attempt < self.max_retries - 1:
                wait_time = (2 ** attempt) * 2
                logger.warning(
                    f"Retrying LLM providers for task {self.task.value} in {wait_time}s"
                )
                await asyncio.sleep(wait_time)

        if last_error is not None:
            err_str = str(last_error)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate_limit" in err_str.lower():
                raise LLMRateLimitError(
                    f"All LLM providers are rate-limited for task '{self.task.value}'. "
                    f"Last error: {last_error}"
                ) from last_error
            raise last_error

        raise RuntimeError(
            f"No LLM available for task '{self.task.value}' after {self.max_retries} retries. "
            "Check that at least one API key is configured in .env"
        )

    def _call_llm(self, llm, data, method_name: str, config=None, **kwargs):
        method = getattr(llm, method_name)
        params = inspect.signature(method).parameters
        if "config" in params:
            return method(data, config=config, **kwargs)
        return method(data, **kwargs)

    async def _call_llm_async(self, llm, data, method_name: str, config=None, **kwargs):
        method = getattr(llm, method_name)
        params = inspect.signature(method).parameters
        if "config" in params:
            return await method(data, config=config, **kwargs)
        return await method(data, **kwargs)


def get_llm(
    task: TaskType,
    temperature: float = 0.0,
) -> BaseChatModel:
    """
    Get the best available LLM for the given task type.
    Uses a runtime fallback wrapper so provider errors during invocation are
    retried against the next configured model.
    """
    candidates = _MODEL_REGISTRY.get(task, _MODEL_REGISTRY[TaskType.CHAT])
    return FallbackChatModel(task, candidates, temperature=temperature, max_retries=3)


def get_llm_with_retry(
    task: TaskType,
    temperature: float = 0.0,
    max_retries: int = 3,
) -> BaseChatModel:
    """
    Get an LLM with automatic retry on provider errors.
    The router tries the primary provider first, then falls back through the
    candidate list. If a provider is configured but fails at runtime (for example
    a 429 quota error), the next provider is attempted before giving up.
    """
    candidates = _MODEL_REGISTRY.get(task, _MODEL_REGISTRY[TaskType.CHAT])
    return FallbackChatModel(task, candidates, temperature=temperature, max_retries=max_retries)


def get_embedding_client():
    """Get the Gemini embedding client (google-genai SDK, not LangChain)."""
    from google import genai
    return genai.Client(api_key=settings.gemini_api_key)


async def generate_embedding(text: str) -> list[float]:
    """Generate a 768-dim embedding using Gemini Embedding — optimized for queries."""
    client = get_embedding_client()

    def _sync_embed():
        result = client.models.embed_content(
            model=settings.embedding_model,
            contents=text,
            config={
                "task_type": "RETRIEVAL_QUERY",  # Optimized for query (not document)
                "output_dimensionality": settings.embedding_dimensions,
            },
        )
        return result.embeddings[0].values

    # Run the synchronous SDK call in a thread so the async event loop isn't blocked.
    return await asyncio.to_thread(_sync_embed)


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for multiple query strings in a SINGLE API call.

    Instead of N separate generate_embedding() calls (N round-trips to Gemini),
    this sends all texts in one batch request and returns N embeddings.

    Used by:
      - policy_analyzer.py: batch-embed all targeted_queries at once
      - _warm_query_cache(): pre-embed all fixed DENIAL_QUERIES at startup

    Args:
        texts: List of query strings to embed.

    Returns:
        List of 768-dim embedding vectors, one per input text, in the same order.
    """
    if not texts:
        return []

    client = get_embedding_client()

    def _sync_batch_embed():
        result = client.models.embed_content(
            model=settings.embedding_model,
            contents=texts,
            config={
                "task_type": "RETRIEVAL_QUERY",
                "output_dimensionality": settings.embedding_dimensions,
            },
        )
        return [emb.values for emb in result.embeddings]

    return await asyncio.to_thread(_sync_batch_embed)


async def embed_document_chunks(chunks: list[dict], max_pages: int = 200) -> list[dict]:
    """
    Embed a list of page-aware text chunks using Gemini Embedding.

    Each input chunk must have 'chunk_text', 'page_number', and 'chunk_index'.
    Returns the same list with 'embedding' added to each chunk.

    Uses RETRIEVAL_DOCUMENT task_type (not QUERY) to optimize for storage.
    Processes in batches of 50 with inter-batch delays to respect rate limits.
    Includes exponential backoff on 429 RESOURCE_EXHAUSTED errors.

    Args:
        chunks: List of chunk dicts with chunk_text, page_number, chunk_index.
        max_pages: Soft cap — chunks beyond this page number are skipped to prevent
                   runaway billing on extremely long documents. Default is 200 pages.
    """
    client = get_embedding_client()
    embedded_chunks = []
    batch_size = 50
    BATCH_DELAY_S = 0.5   # 500ms between batches — stay under 100 req/min free tier
    MAX_RETRIES = 3

    # Soft page cap — skip chunks from pages beyond max_pages
    filtered = [c for c in chunks if c.get("page_number", 0) <= max_pages]
    if len(filtered) < len(chunks):
        skipped = len(chunks) - len(filtered)
        logger.warning(
            f"embed_document_chunks: Skipped {skipped} chunks beyond page {max_pages} "
            f"(soft cap). Total chunks to embed: {len(filtered)}"
        )

    for i in range(0, len(filtered), batch_size):
        batch = filtered[i: i + batch_size]
        texts = [c["chunk_text"] for c in batch]
        batch_num = i // batch_size + 1
        total_batches = (len(filtered) + batch_size - 1) // batch_size

        success = False
        for attempt in range(MAX_RETRIES):
            try:
                # Run the synchronous SDK call in a thread pool so the event loop
                # isn't blocked during multi-batch document ingestion.
                def _batch_embed(t=texts):
                    return client.models.embed_content(
                        model=settings.embedding_model,
                        contents=t,
                        config={
                            "task_type": "RETRIEVAL_DOCUMENT",  # Optimized for document storage
                            "output_dimensionality": settings.embedding_dimensions,
                        },
                    )

                result = await asyncio.to_thread(_batch_embed)
                for chunk, emb in zip(batch, result.embeddings):
                    embedded_chunks.append({**chunk, "embedding": emb.values})
                success = True
                logger.debug(f"Batch {batch_num}/{total_batches} embedded ({len(batch)} chunks)")
                break

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = (2 ** attempt) * 5  # 5s, 10s, 20s
                    logger.warning(
                        f"Embedding batch {batch_num} rate-limited (attempt {attempt + 1}/{MAX_RETRIES}). "
                        f"Waiting {wait}s before retry..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Embedding batch {batch_num} failed (non-retryable): {e}")
                    break

        if not success:
            logger.error(f"Embedding batch {batch_num} failed after {MAX_RETRIES} retries — inserting without embeddings")
            for chunk in batch:
                embedded_chunks.append({**chunk, "embedding": None})

        # Inter-batch delay to stay within Gemini free-tier rate limits
        if i + batch_size < len(filtered):
            await asyncio.sleep(BATCH_DELAY_S)

    valid = sum(1 for c in embedded_chunks if c.get("embedding") is not None)
    logger.info(
        f"embed_document_chunks: {valid}/{len(filtered)} chunks embedded successfully "
        f"({len(chunks) - len(filtered)} skipped by page cap)"
    )
    return embedded_chunks
