"""
PolicyCrab API — FastAPI Application Entry Point

AI-driven health insurance claims engine for the US market.
Evaluates eligibility, estimates costs, and drafts formal appeals.
"""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.cloudflare import CloudflareMiddleware

# LangSmith tracing is only useful when a valid API key is configured.
# If tracing is enabled without credentials, the client will emit 403 noise on every request.
if os.environ.get("LANGCHAIN_TRACING_V2") == "true" and not (
    os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
):
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

from app.api.router import api_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
)
# Access log always at INFO regardless of debug flag
logging.getLogger("policycrab.access").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("🚀 Starting PolicyCrab v0.1.0")
    logger.info(f"   Supabase: {settings.supabase_url}")
    logger.info(f"   LLM Fast: {settings.llm_fast_model}")
    logger.info(f"   LLM Quality: {settings.llm_quality_model}")

    if os.environ.get("LANGCHAIN_TRACING_V2") == "true":
        logger.info(f"   Observability: LangSmith tracing ENABLED (Project: {os.environ.get('LANGCHAIN_PROJECT', 'default')}) ✅")
    else:
        logger.info("   Observability: LangSmith tracing DISABLED ⚠️")

    if settings.cloudflare_enabled:
        logger.info(f"   Cloudflare: ENABLED (cloudflare_only={settings.cloudflare_only}) 🛡️")
    else:
        logger.info("   Cloudflare: DISABLED (direct access mode) ⚠️")

    # Validate critical connections on startup
    try:
        from app.services.supabase_client import get_supabase_client
        client = get_supabase_client()
        result = client.table("knowledge_chunks").select("id", count="exact").limit(1).execute()
        count = result.count if result.count is not None else len(result.data)
        logger.info(f"   Knowledge Base: {count} chunks loaded ✅")
    except Exception as e:
        logger.error(f"   Knowledge Base connection failed: {e}")

    # Pre-warm the Policy Analyzer's embedding cache for fixed denial queries.
    # This pre-computes embeddings for all DENIAL_QUERIES at startup so they are
    # never re-embedded at runtime (saves ~6 embedding API calls per denied claim).
    try:
        from app.agents.policy_analyzer import warm_query_cache
        await warm_query_cache()
        logger.info("   Query Embedding Cache: warmed ✅")
    except Exception as e:
        logger.warning(f"   Query Embedding Cache: failed to warm (will embed at runtime): {e}")

    yield

    logger.info(f"👋 Shutting down {settings.app_name}")


# ── Create FastAPI App ────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-driven health insurance claims engine for the US market. "
        "Evaluates patient eligibility, estimates costs using deterministic logic, "
        "and drafts formal appeals for denied claims using RAG-powered agents."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Cloudflare IP Trust Middleware ────────────────────────────────
# Must be registered BEFORE logging middleware so the real client IP
# is available when the log line is emitted.
app.add_middleware(
    CloudflareMiddleware,
    enabled=settings.cloudflare_enabled,
    cloudflare_only=settings.cloudflare_only,
)

# ── Request Logging Middleware ────────────────────────────────────
# Registered after CORS so status codes reflect the actual response.
app.add_middleware(RequestLoggingMiddleware)

# ── Include API Routes ────────────────────────────────────────────
app.include_router(api_router)

@app.get("/health", tags=["system"])
async def health_check():
    """Simple health check endpoint for Heroku deployment monitors."""
    return {"status": "ok", "service": "policycrab-backend"}
