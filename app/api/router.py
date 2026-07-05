"""
API Router — aggregates all route modules and provides the health check.
"""

from datetime import datetime, timezone
from fastapi import APIRouter

from app.config import settings
from app.api.policy_routes import router as policy_router
from app.api.claim_routes import router as claim_router
from app.api.chat_routes import router as chat_router
from app.api.history_routes import router as history_router

api_router = APIRouter()

# Include sub-routers
api_router.include_router(policy_router)
api_router.include_router(claim_router)
api_router.include_router(chat_router)
api_router.include_router(history_router)


@api_router.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint — verifies the server is running."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/api/knowledge/search", tags=["Knowledge Base"])
async def search_knowledge(q: str, domain: str | None = None, jurisdiction: str | None = None, limit: int = 5):
    """
    Search the knowledge base using semantic similarity.
    Useful for debugging and verifying RAG retrieval quality.
    """
    from app.services.llm_router import generate_embedding
    from app.services.supabase_client import search_knowledge_base

    # Generate query embedding
    query_embedding = await generate_embedding(q)

    # Search with optional metadata filters
    results = await search_knowledge_base(
        query_embedding=query_embedding,
        filter_domain=domain,
        filter_jurisdiction=jurisdiction,
        match_count=limit,
    )

    return {
        "query": q,
        "results": [
            {
                "concept_id": r["concept_id"],
                "title": r["title"],
                "similarity": round(r["similarity"], 4),
                "domain": r["domain"],
                "jurisdiction": r["jurisdiction"],
                "semantic_summary": r["semantic_summary"],
            }
            for r in results
        ],
    }
