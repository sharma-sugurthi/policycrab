"""
RAG Search Tool — retrieves relevant knowledge chunks from the
Supabase pgvector knowledge base using semantic similarity.

This is the primary retrieval tool for all agents, especially
the Grievance Agent (for regulatory citations) and Chat Agent
(for answering patient questions).
"""

from langchain_core.tools import tool
from app.services.llm_router import generate_embedding
from app.services.supabase_client import search_knowledge_base


@tool
async def search_insurance_knowledge(
    query: str,
    domain: str | None = None,
    jurisdiction: str | None = None,
    num_results: int = 5,
) -> str:
    """Search the US health insurance knowledge base for regulations, laws, and procedures.

    Use this tool to find information about:
    - Insurance regulations (ERISA, ACA, No Surprises Act, HIPAA)
    - Appeal procedures and deadlines
    - Cost-sharing mechanics (deductibles, coinsurance, OOP max)
    - Medicare/Medicaid rules
    - Denial codes (CARC/RARC) and their meanings
    - Consumer defense strategies
    - Insurer-specific denial patterns

    Args:
        query: Natural language search query describing what you need.
        domain: Optional filter — "Health", "Regulatory", or None for all.
        jurisdiction: Optional filter — "Federal", "State-Specific", "US-General", or None for all.
        num_results: Number of results to return (default 5, max 10).
    """
    # Generate embedding for the query
    query_embedding = await generate_embedding(query)

    # Search the knowledge base
    results = await search_knowledge_base(
        query_embedding=query_embedding,
        filter_domain=domain,
        filter_jurisdiction=jurisdiction,
        match_count=min(num_results, 10),
    )

    if not results:
        return "No relevant knowledge found for this query. Try rephrasing or broadening the search."

    # Format results for the LLM
    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append(
            f"[{i}] {r['title']} (similarity: {r['similarity']:.3f})\n"
            f"    Domain: {r['domain']} | Jurisdiction: {r['jurisdiction']}\n"
            f"    Summary: {r['semantic_summary']}\n"
            f"    Full Content:\n{r['full_content']}\n"
        )

    return "\n---\n".join(formatted)
