"""
Supabase client singleton — used for both application data and vector search.

Exposes two search surfaces:
  1. search_knowledge_base()     — static regulatory/legal knowledge (ERISA, ACA, NSA)
  2. insert_policy_chunks()      — store user-uploaded policy chunks per session
  3. search_policy_document()    — semantic search within a session's policy chunks
  4. delete_policy_session()     — cleanup after analysis is complete
"""

import logging
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_supabase_client() -> Client:
    """Get or create the Supabase client singleton."""
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


# ── Regulatory Knowledge Base (static) ───────────────────────────

async def search_knowledge_base(
    query_embedding: list[float],
    filter_domain: str | None = None,
    filter_jurisdiction: str | None = None,
    match_count: int = 5,
) -> list[dict]:
    """
    Hybrid vector + metadata search against the knowledge_chunks table.
    Uses the search_knowledge() Postgres function created in the migration.
    """
    client = get_supabase_client()

    params = {
        "query_embedding": query_embedding,
        "match_count": match_count,
    }
    if filter_domain:
        params["filter_domain"] = filter_domain
    if filter_jurisdiction:
        params["filter_jurisdiction"] = filter_jurisdiction

    result = client.rpc("search_knowledge", params).execute()
    return result.data or []


# ── User Policy Document Store (session-scoped) ───────────────────

async def insert_policy_chunks(
    session_id: str,
    chunks: list[dict],
) -> int:
    """
    Bulk-insert embedded policy document chunks into the policy_chunks table.

    Each chunk dict must contain:
      - page_number (int): 1-indexed page number from the PDF
      - chunk_index (int): position of the chunk within the page
      - chunk_text  (str): the raw text content
      - embedding   (list[float]): 768-dim Gemini embedding vector
      - carrier_name (str, optional): for denormalized filtering
      - plan_name    (str, optional): for denormalized filtering

    Returns the number of rows inserted.
    """
    client = get_supabase_client()

    rows = []
    for chunk in chunks:
        rows.append({
            "session_id":   session_id,
            "page_number":  chunk["page_number"],
            "chunk_index":  chunk["chunk_index"],
            "chunk_text":   chunk["chunk_text"],
            "embedding":    chunk["embedding"],
            "carrier_name": chunk.get("carrier_name"),
            "plan_name":    chunk.get("plan_name"),
        })

    # Supabase upsert with on-conflict ignore (idempotent re-runs)
    result = client.table("policy_chunks").upsert(rows, on_conflict="session_id,page_number,chunk_index").execute()
    inserted = len(result.data) if result.data else 0
    logger.info(f"Supabase: Inserted {inserted} policy chunks for session '{session_id}'")
    return inserted


async def search_policy_document(
    session_id: str,
    query_embedding: list[float],
    match_count: int = 6,
    similarity_threshold: float = 0.30,
) -> list[dict]:
    """
    Semantic search within the uploaded policy document for a specific session.

    Uses the search_policy_document() Postgres RPC function defined in
    migration 002_user_policy_vector.sql.

    Returns ranked list of dicts with keys:
      page_number, chunk_index, chunk_text, similarity
    """
    client = get_supabase_client()

    params = {
        "p_session_id":        session_id,
        "query_embedding":     query_embedding,
        "match_count":         match_count,
        "similarity_threshold": similarity_threshold,
    }

    result = client.rpc("search_policy_document", params).execute()
    return result.data or []


async def delete_policy_session(session_id: str) -> None:
    """
    Remove all policy chunks for a given session from Supabase.
    Call after analysis is complete if you want to avoid data accumulation.
    """
    client = get_supabase_client()
    client.rpc("delete_policy_session", {"p_session_id": session_id}).execute()
    logger.info(f"Supabase: Deleted all policy chunks for session '{session_id}'")
