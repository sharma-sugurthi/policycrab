"""
Policy ingestion background task — runs inside the FastAPI web dyno.

Uses asyncio (no separate worker process) so it works within Heroku Eco's
1,000 hour/month limit without any additional cost.
"""

import logging

from app.worker import (
    complete_task,
    fail_task,
    update_progress,
)

logger = logging.getLogger(__name__)


async def run_policy_ingestion(
    task_id: str,
    pdf_text: str,
    session_id: str,
    user_id: str | None = None,
) -> None:
    """
    Async background coroutine: run the full policy ingestion pipeline.

    Progress is written to Redis/memory so GET /api/tasks/{task_id} can
    return live updates while this coroutine runs in the background.
    """
    try:
        update_progress(task_id, 10, "Initializing policy ingestion pipeline...",
                        session_id=session_id)

        from app.agents.graph import get_policy_ingestion_graph
        graph = get_policy_ingestion_graph()

        update_progress(task_id, 20, "Chunking document and generating embeddings...",
                        session_id=session_id)

        initial_state = {
            "messages": [],
            "raw_policy_text": pdf_text,
            "raw_claim_text": "",
            "policy_profile": None,
            "claim_case": None,
            "allowed_amount": None,
            "cost_breakdown": None,
            "appeal_output": None,
            "current_phase": "ingestion",
            "route_decision": "",
            "errors": [],
            "extraction_warnings": [],
            "extraction_confidence": None,
            "explanations": {},
            "session_id": session_id,
            "user_id": user_id,
        }

        update_progress(task_id, 35, "Running AI extraction agents...",
                        session_id=session_id)

        result = await graph.ainvoke(initial_state)

        update_progress(task_id, 85, "Saving policy profile...",
                        session_id=session_id)

        # Persist to Supabase if user is authenticated
        if result.get("policy_profile") and user_id:
            try:
                from app.services.user_data import create_user_policy
                create_user_policy(
                    user_id,
                    result["policy_profile"],
                    session_id=result.get("session_id", session_id),
                )
            except Exception as db_err:
                logger.error(f"Policy task: Failed to persist policy: {db_err}")
                result.setdefault("errors", []).append(
                    "Policy parsed but could not be saved. Please retry."
                )

        payload = {
            "success": bool(result.get("policy_profile")),
            "policy_profile": result.get("policy_profile"),
            "explanation": result.get("explanations", {}).get("ingestion"),
            "extraction_warnings": result.get("extraction_warnings", []),
            "extraction_confidence": result.get("extraction_confidence"),
            "errors": result.get("errors", []),
            "session_id": result.get("session_id", session_id),
            "policy_indexed": result.get("policy_indexed", False),
            "policy_page_count": result.get("policy_page_count"),
        }

        complete_task(task_id, payload)
        logger.info(f"Policy ingestion task {task_id} completed successfully")

    except Exception as exc:
        logger.error(f"Policy ingestion task {task_id} failed: {exc}", exc_info=True)
        fail_task(task_id, str(exc))
