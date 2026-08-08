"""
Claim evaluation background task — runs inside the FastAPI web dyno.

Uses asyncio (no separate worker process) so it works within Cloud Run's
1,000 hour/month limit without any additional cost.
"""

import logging

from app.worker import (
    complete_task,
    fail_task,
    update_progress,
)

logger = logging.getLogger(__name__)


async def run_claim_evaluation(
    task_id: str,
    claim_description: str,
    policy_profile: dict | None = None,
    allowed_amount: float | None = None,
    benchmark_policy_excerpt: str | None = None,
    session_id: str | None = None,
    policy_indexed: bool = False,
    user_id: str | None = None,
) -> None:
    """
    Async background coroutine: run the full claim evaluation pipeline.

    The 6-node LangGraph pipeline (intake → cost → policy_analyzer →
    triage → grievance → explanation) runs as an asyncio task inside
    the web dyno. Progress is written to Redis for live polling.
    """
    try:
        update_progress(task_id, 5, "Initializing claim evaluation...",
                        pipeline_phase="intake")

        from app.agents.graph import get_claim_evaluation_graph
        graph = get_claim_evaluation_graph()

        update_progress(task_id, 15, "Agent: Extracting structured claim data...",
                        pipeline_phase="intake")

        initial_state = {
            "messages": [],
            "raw_policy_text": "",
            "raw_claim_text": claim_description,
            "benchmark_policy_excerpt": benchmark_policy_excerpt,
            "policy_profile": policy_profile,
            "claim_case": None,
            "allowed_amount": allowed_amount,
            "cost_breakdown": None,
            "appeal_output": None,
            "current_phase": "intake",
            "route_decision": "",
            "errors": [],
            "extraction_warnings": [],
            "extraction_confidence": None,
            "explanations": {},
            "session_id": session_id,
            "policy_indexed": policy_indexed,
        }

        result = await graph.ainvoke(initial_state)

        update_progress(task_id, 90, "Finalizing evaluation results...",
                        pipeline_phase=result.get("current_phase", "complete"))

        # Persist to Supabase
        if result.get("claim_case") and user_id:
            try:
                from app.services.user_data import create_user_claim
                create_user_claim(
                    user_id=user_id,
                    claim_description=claim_description,
                    cost_breakdown=result.get("cost_breakdown"),
                    appeal_output=result.get("appeal_output"),
                    route_decision=result.get("route_decision"),
                )
            except Exception as db_err:
                logger.error(f"Claim task: Failed to persist claim: {db_err}")
                result.setdefault("errors", []).append(
                    "Claim evaluated, but could not be saved to history."
                )

        explanations = result.get("explanations", {})
        explanation = (
            explanations.get("appeal")
            or explanations.get("calculation")
            or explanations.get("intake")
        )

        complete_task(task_id, {
            "success": bool(result.get("claim_case")),
            "claim_case": result.get("claim_case"),
            "cost_breakdown": result.get("cost_breakdown"),
            "appeal_output": result.get("appeal_output"),
            "explanation": explanation,
            "route_decision": result.get("route_decision"),
            "errors": result.get("errors", []),
        })
        logger.info(f"Claim evaluation task {task_id} completed successfully")

    except Exception as exc:
        logger.error(f"Claim evaluation task {task_id} failed: {exc}", exc_info=True)
        fail_task(task_id, str(exc))
