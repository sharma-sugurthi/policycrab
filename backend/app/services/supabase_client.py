"""
Supabase client singleton — used for both application data and vector search.

Exposes these search surfaces:
  1. search_knowledge_base()     — static regulatory/legal knowledge (ERISA, ACA, NSA)
  2. insert_policy_chunks()      — store user-uploaded policy chunks per session
  3. search_policy_document()    — semantic search within a session's policy chunks
  4. fetch_structural_anchor()   — keyword-based section retrieval (EXCLUSIONS, APPEALS, etc.)
  5. delete_policy_session()     — cleanup after analysis is complete
  6. save_policy_session()       — persist PolicyProfile JSON for returning users
  7. load_policy_session()       — retrieve cached PolicyProfile by session_id
"""

import json
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
      - section_heading (str | None): canonical section tag (e.g. 'EXCLUSIONS', 'APPEALS')
      - carrier_name (str, optional): for denormalized filtering
      - plan_name    (str, optional): for denormalized filtering

    Returns the number of rows inserted.
    """
    client = get_supabase_client()

    rows = []
    for chunk in chunks:
        rows.append({
            "session_id":      session_id,
            "page_number":     chunk["page_number"],
            "chunk_index":     chunk["chunk_index"],
            "chunk_text":      chunk["chunk_text"],
            "embedding":       chunk["embedding"],
            "section_heading": chunk.get("section_heading"),
            "carrier_name":    chunk.get("carrier_name"),
            "plan_name":       chunk.get("plan_name"),
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
    section_filter: str | None = None,
) -> list[dict]:
    """
    Semantic search within the uploaded policy document for a specific session.

    Uses the search_policy_document() Postgres RPC function.

    Args:
        session_id: Session scope for the policy document.
        query_embedding: 768-dim query embedding vector.
        match_count: Max results to return.
        similarity_threshold: Minimum cosine similarity (0.0–1.0).
        section_filter: Optional keyword filter on section_heading column.
                        When provided, only chunks from matching sections are returned.
                        Example: 'EXCLUSION' matches section_heading='EXCLUSIONS'.

    Returns:
        Ranked list of dicts with keys:
          page_number, chunk_index, chunk_text, section_heading, similarity
    """
    client = get_supabase_client()

    params = {
        "p_session_id":         session_id,
        "query_embedding":      query_embedding,
        "match_count":          match_count,
        "similarity_threshold": similarity_threshold,
    }

    # Only pass section_filter if provided — the RPC has a DEFAULT NULL
    if section_filter is not None:
        params["section_filter"] = section_filter

    result = client.rpc("search_policy_document", params).execute()
    return result.data or []


async def fetch_structural_anchor(
    session_id: str,
    section_type: str,
    max_chunks: int = 4,
) -> list[dict]:
    """
    Fetch chunks from a specific policy section by keyword match on section_heading.

    This does NOT use semantic similarity — it retrieves by structural position
    in the document. Used to guarantee that EXCLUSIONS, APPEALS, and DEFINITIONS
    sections are always present in the Policy Analyzer's context.

    Args:
        session_id: Session scope.
        section_type: Canonical section keyword (e.g. 'EXCLUSIONS', 'APPEALS', 'DEFINITIONS').
        max_chunks: Maximum chunks to return from this section.

    Returns:
        List of dicts with keys: page_number, chunk_index, chunk_text, section_heading
        Ordered by page_number ASC (document reading order).
    """
    client = get_supabase_client()

    result = client.rpc("fetch_policy_section", {
        "p_session_id": session_id,
        "section_type":  section_type,
        "max_chunks":    max_chunks,
    }).execute()

    chunks = result.data or []
    if chunks:
        logger.debug(
            f"Supabase: Structural anchor '{section_type}' returned {len(chunks)} chunks "
            f"for session '{session_id}'"
        )
    return chunks


async def delete_policy_session(session_id: str) -> None:
    """
    Remove all policy chunks for a given session from Supabase.
    Call after analysis is complete if you want to avoid data accumulation.
    """
    client = get_supabase_client()
    client.rpc("delete_policy_session", {"p_session_id": session_id}).execute()
    logger.info(f"Supabase: Deleted all policy chunks for session '{session_id}'")


# ── Policy Session Persistence (Priority 5) ──────────────────────

async def save_policy_session(
    session_id: str,
    user_id: str,
    policy_profile: dict,
) -> None:
    """
    Persist a PolicyProfile JSON so returning users skip Phase 2 extraction.

    Upserts into the policy_sessions table — if the session already exists,
    the profile is updated (handles re-uploads gracefully).
    """
    client = get_supabase_client()

    try:
        client.table("policy_sessions").upsert({
            "session_id":     session_id,
            "user_id":        user_id,
            "policy_profile": json.dumps(policy_profile) if isinstance(policy_profile, dict) else policy_profile,
        }, on_conflict="session_id").execute()

        logger.info(f"Supabase: PolicyProfile saved for session '{session_id}'")
    except Exception as e:
        logger.warning(f"Supabase: Failed to save policy session (non-fatal): {e}")


async def load_policy_session(session_id: str) -> dict | None:
    """
    Load a previously persisted PolicyProfile by session_id.

    Returns the policy_profile dict if found, None otherwise.
    Used at the start of claim evaluation to skip Phase 2 extraction
    for returning users.
    """
    client = get_supabase_client()

    try:
        result = (
            client.table("policy_sessions")
            .select("policy_profile")
            .eq("session_id", session_id)
            .limit(1)
            .execute()
        )

        if result.data and len(result.data) > 0:
            profile = result.data[0].get("policy_profile")
            if isinstance(profile, str):
                profile = json.loads(profile)
            logger.info(f"Supabase: Loaded cached PolicyProfile for session '{session_id}'")
            return profile

    except Exception as e:
        logger.warning(f"Supabase: Failed to load policy session (non-fatal): {e}")

    return None
