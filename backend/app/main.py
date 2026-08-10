"""
PolicyCrab API — FastAPI Application Entry Point

AI-driven health insurance claims engine for the US market.
Evaluates eligibility, estimates costs, and drafts formal appeals.
"""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
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

# ── Global Empathetic Exception Guards ────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Intercept all unhandled server or AI provider errors and translate them into friendly UX messaging."""
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    error_str = str(exc).lower()
    if any(k in error_str for k in ["429", "quota", "rate limit", "resource_exhausted", "too many requests", "traffic"]):
        message = "We are currently experiencing high AI traffic! Please give us just a moment and try again shortly."
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    elif any(k in error_str for k in ["timeout", "timed out", "too large", "context length", "token limit"]):
        message = "We encountered a processing timeout due to high load or document size. Please try again later, or try uploading a smaller or compressed document!"
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
    else:
        message = "Our backend servers are currently loading or undergoing brief maintenance. Please try again shortly! The problem is definitely with our systems, not with your request or data."
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
    return JSONResponse(
        status_code=status_code,
        content={"error": message, "code": "SERVICE_NOTICE", "detail": message}
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
    """Simple health check endpoint for deployment monitors."""
    return {"status": "ok", "service": "policycrab-backend"}

from fastapi.responses import PlainTextResponse

@app.get("/robots.txt", response_class=PlainTextResponse, tags=["system"])
async def robots_txt():
    """Disallow all web crawlers."""
    return "User-agent: *\nDisallow: /\n"

@app.get("/.env", tags=["system"])
async def fake_env():
    """Catch-all for bot scanners looking for .env files."""
    return JSONResponse(status_code=404, content={"error": "Not Found"})
