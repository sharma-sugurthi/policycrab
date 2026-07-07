"""
Multi-LLM Router — intelligent model selection with automatic fallback.

Strategy:
- Each task type maps to an ordered list of (provider, model) pairs.
- The router tries the primary model first.
- On rate limit (429) or error, it falls back to the next model.
- All calls are logged for observability.
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


# ── Model Registry ────────────────────────────────────────────────
# Each task maps to an ordered list of (provider, model_name, api_key_attr)
# The router tries them in order, falling back on errors.

_MODEL_REGISTRY: dict[TaskType, list[dict]] = {
    TaskType.EXTRACTION: [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "cerebras", "model": "llama3.1-8b"},
        {"provider": "gemini", "model": "gemini-2.5-flash"},
    ],
    TaskType.TOOL_CALLING: [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "cerebras", "model": "llama3.1-8b"},
        {"provider": "gemini", "model": "gemini-2.5-flash"},
    ],
    TaskType.LEGAL_WRITING: [
        {"provider": "gemini", "model": "gemini-2.5-pro"}, # Best for long-form reasoning
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    ],
    TaskType.EXPLANATION: [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "gemini", "model": "gemini-2.5-flash"},
    ],
    TaskType.CHAT: [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "cerebras", "model": "llama3.1-8b"},
        {"provider": "gemini", "model": "gemini-2.5-flash"},
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
