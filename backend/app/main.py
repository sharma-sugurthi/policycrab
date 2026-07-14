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
from app.api.router import api_router
from app.middleware.logging import RequestLoggingMiddleware

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

    # Validate critical connections on startup
    try:
        from app.services.supabase_client import get_supabase_client
        client = get_supabase_client()
        result = client.table("knowledge_chunks").select("id", count="exact").limit(1).execute()
        count = result.count if result.count is not None else len(result.data)
        logger.info(f"   Knowledge Base: {count} chunks loaded ✅")
    except Exception as e:
        logger.error(f"   Knowledge Base connection failed: {e}")

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

# ── Request Logging Middleware ────────────────────────────────────
# Registered after CORS so status codes reflect the actual response.
app.add_middleware(RequestLoggingMiddleware)

# ── Include API Routes ────────────────────────────────────────────
app.include_router(api_router)

@app.get("/health", tags=["system"])
async def health_check():
    """Simple health check endpoint for Render/HuggingFace deployment monitors."""
    return {"status": "ok", "service": "policycrab-backend"}
