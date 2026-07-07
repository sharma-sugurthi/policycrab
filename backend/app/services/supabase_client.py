"""
Supabase client singleton — used for both application data and vector search.
"""

from supabase import create_client, Client
from app.config import settings


_client: Client | None = None


def get_supabase_client() -> Client:
    """Get or create the Supabase client singleton."""
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


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
