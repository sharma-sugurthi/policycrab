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
    moonshot_api_key: str = ""      # Kimi (Moonshot AI)
    siliconflow_api_key: str = ""   # Aggregator (free Qwen 72B)
    grok_api_key: str = ""          # x.ai
    tavily_api_key: str = ""        # Web Search Tool

    # ── Application ───────────────────────────────────────────────
    app_name: str = "US Policy Claimer"
    app_version: str = "0.1.0"
    debug: bool = False
    allow_benchmark_auth: bool = False
    cors_origins: str | list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://policycrab.tech",
        "https://www.policycrab.tech",
        "https://api.policycrab.tech",
    ]

    # ── Email (Resend) ────────────────────────────────────────────
    resend_api_key: str = ""
    email_from: str = "PolicyCrab <info@policycrab.tech>"

    # ── Redis (task status tracking only — no worker dyno needed) ──
    # Upstash free tier: 10K commands/day, 256MB. Used only for
    # persisting background task progress/results inside the web dyno.
    redis_url: str = ""  # Set to your Upstash rediss:// URL in production

    # ── Cloudflare ─────────────────────────────────────────────────
    cloudflare_enabled: bool = False   # Master switch — activates CF middleware
    cloudflare_only: bool = False      # Block non-CF traffic (set True after DNS migration)

    # ── Admin Authorization (configured via ADMIN_EMAILS environment variable) ──────────
    admin_emails: str = ""

    # ── Organizations (team workspaces) ───────────────────────────
    # Off by default: every /api/orgs endpoint returns 404 and the X-Org-Id
    # header is ignored, so existing single-user behaviour is untouched.
    # Requires supabase/migrations/009_create_organizations.sql.
    orgs_enabled: bool = False
    # Public URL of the frontend; used to build invitation links.
    app_base_url: str = "https://policycrab.tech"
    org_invitation_ttl_days: int = 7

    google_cloud_project: str = ""
    gcp_location: str = "us-east1"

    @property
    def parsed_cors_origins(self) -> list[str]:
        if isinstance(self.cors_origins, str):
            return [x.strip() for x in self.cors_origins.split(",") if x.strip()]
        return self.cors_origins

    @property
    def parsed_admin_emails(self) -> set[str]:
        if not self.admin_emails:
            return set()
        return {
            x.strip().strip("'").strip('"').lower()
            for x in self.admin_emails.split(",")
            if x.strip()
        }

    # ── Accuracy Core (appeal QA) ─────────────────────────────────
    # How the citation verifier treats statutes the LLM cited that are not in
    # the verified allowlist or the retrieved knowledge chunks:
    #   "annotate" (default) — keep the letter, insert a visible [VERIFY: ...] marker
    #   "strip"              — remove unverified citations from letter + list
    #   "off"                — report only, do not touch the letter
    citation_unverified_policy: str = "annotate"
    # Minimum fuzzy-match ratio for a quoted policy clause to count as grounded
    # in the retrieved policy chunks (0.0-1.0).
    citation_policy_fuzzy_threshold: float = 0.85
    # Extraction quality gate before drafting:
    #   "off"   — never evaluate
    #   "warn"  (default) — draft anyway, attach a missing-information checklist
    #   "block" — return the checklist instead of a letter when critical data is missing
    quality_gate_mode: str = "warn"

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
