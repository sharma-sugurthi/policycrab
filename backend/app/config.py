"""
Application configuration — loads all secrets and settings from .env
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All application settings, loaded from environment variables / .env file."""

    # ── Supabase ──────────────────────────────────────────────────
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str

    # ── Database ──────────────────────────────────────────────────
    database_url: str | None = None

    # ── Gemini ────────────────────────────────────────────────────
    gemini_api_key: str

    # ── Multi-LLM Provider Keys (optional — used by model router) ─
    groq_api_key: str = ""
    cerebras_api_key: str = ""
    openrouter_api_key: str = ""
    grok_api_key: str = ""          # x.ai

    # ── Application ───────────────────────────────────────────────
    app_name: str = "US Policy Claimer"
    app_version: str = "0.1.0"
    debug: bool = False
    cors_origins: str | list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://policycrab.tech",
        "https://www.policycrab.tech",
    ]

    # ── Email (Resend) ────────────────────────────────────────────
    resend_api_key: str = ""
    email_from: str = "PolicyCrab <info@policycrab.tech>"

    @property
    def parsed_cors_origins(self) -> list[str]:
        if isinstance(self.cors_origins, str):
            return [x.strip() for x in self.cors_origins.split(",") if x.strip()]
        return self.cors_origins

    # ── LLM Model Defaults ────────────────────────────────────────
    llm_fast_model: str = "gemini-2.5-flash"
    llm_quality_model: str = "gemini-2.5-pro"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton instance — import this everywhere
settings = Settings()
