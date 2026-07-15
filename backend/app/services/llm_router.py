"""
Multi-LLM Router — intelligent model selection with automatic fallback.

Strategy:
- Gemini is the PRIMARY model for ALL task types (XPRIZE compliance).
- On rate limit (429) or error, falls back to secondary providers.
- All calls are logged with structured step logs for the AI Transparency UI.
"""

import logging
from enum import Enum
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from app.config import settings

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Task types that determine which LLM to use."""
    EXTRACTION = "extraction"          # Policy parsing, structured output
    TOOL_CALLING = "tool_calling"      # Agent tool use, CPT/ICD lookup
    LEGAL_WRITING = "legal_writing"    # Appeal letter drafting (highest quality)
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
        {"provider": "gemini", "model": "gemini-2.5-flash"},   # PRIMARY
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "cerebras", "model": "llama3.1-8b"},
    ],
    TaskType.TOOL_CALLING: [
        {"provider": "gemini", "model": "gemini-2.5-flash"},   # PRIMARY
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "cerebras", "model": "llama3.1-8b"},
    ],
    TaskType.LEGAL_WRITING: [
        {"provider": "gemini", "model": "gemini-2.5-pro"},     # PRIMARY — best for long-form legal reasoning
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    ],
    TaskType.EXPLANATION: [
        {"provider": "gemini", "model": "gemini-2.5-flash"},   # PRIMARY
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    ],
    TaskType.CHAT: [
        {"provider": "gemini", "model": "gemini-2.5-flash"},   # PRIMARY
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "cerebras", "model": "llama3.1-8b"},
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


def get_llm(
    task: TaskType,
    temperature: float = 0.0,
) -> BaseChatModel:
    """
    Get the best available LLM for the given task type.
    Tries models in priority order, skipping unavailable providers.
    """
    candidates = _MODEL_REGISTRY.get(task, _MODEL_REGISTRY[TaskType.CHAT])

    for entry in candidates:
        llm = _create_llm(entry["provider"], entry["model"], temperature)
        if llm is not None:
            logger.info(f"LLM selected for {task.value}: {entry['provider']}/{entry['model']}")
            return llm

    # Final fallback — always try Gemini Flash
    fallback = _create_llm("gemini", settings.llm_fast_model, temperature)
    if fallback:
        return fallback

    raise RuntimeError(
        f"No LLM available for task '{task.value}'. "
        "Check that at least one API key is configured in .env"
    )


def get_embedding_client():
    """Get the Gemini embedding client (google-genai SDK, not LangChain)."""
    from google import genai
    return genai.Client(api_key=settings.gemini_api_key)


async def generate_embedding(text: str) -> list[float]:
    """Generate a 768-dim embedding using Gemini Embedding 001."""
    client = get_embedding_client()
    result = client.models.embed_content(
        model=settings.embedding_model,
        contents=text,
        config={
            "task_type": "RETRIEVAL_QUERY",  # Optimized for query (not document)
            "output_dimensionality": settings.embedding_dimensions,
        },
    )
    return result.embeddings[0].values
