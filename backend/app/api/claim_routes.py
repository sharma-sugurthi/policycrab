"""
Claim API Routes — evaluate claims and calculate costs.
"""

import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.agents.graph import get_claim_evaluation_graph
from app.api.auth import get_current_user
from app.security.rate_limit import rate_limit_user
from app.security.presidio_scrubber import PHIScrubbingError, scrub_phi
from app.services.user_data import create_user_claim

# Per-user: 5 evaluations per 60 seconds
CLAIM_EVALUATE_RATE_LIMIT = rate_limit_user("claim:evaluate", max_requests=5, window_seconds=60)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/claim", tags=["Claims"])


class ClaimEvaluationRequest(BaseModel):
    """Request body for claim evaluation."""
    claim_description: str = Field(
        ...,
        min_length=20,
        description="Patient's description of their healthcare encounter and claim"
    )
    policy_profile: dict | None = Field(
        None,
        description="Previously parsed PolicyProfile (from /api/policy/upload). Required for cost calculation."
    )
    allowed_amount: float | None = Field(
        None,
        gt=0,
        description="Optional EOB/ERA allowed amount. If omitted, the engine uses billed amount as a conservative estimate and labels the result as an estimate.",
    )
    benchmark_policy_excerpt: str | None = Field(
        None,
        description="Hidden field for automated benchmarks. Injects policy excerpt directly, bypassing RAG."
    )
    session_id: str | None = Field(
        None,
        description="Policy RAG session returned by policy upload.",
    )
    policy_indexed: bool = Field(
        False,
        description="Whether the selected policy has searchable document chunks.",
    )


class ClaimEvaluationResponse(BaseModel):
    """Response after claim evaluation pipeline."""
    success: bool
    claim_case: dict | None = None
    cost_breakdown: dict | None = None
    appeal_output: dict | None = None
    explanation: str | None = None
    route_decision: str | None = None
    errors: list[str] = []


@router.post("/evaluate", response_model=ClaimEvaluationResponse)
async def evaluate_claim(
    request: ClaimEvaluationRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(CLAIM_EVALUATE_RATE_LIMIT),
):
    """
    Evaluate a patient's healthcare claim through the full pipeline.

    Flow:
    1. Claim Intake Agent normalizes the description to structured data
    2. Deterministic Cost Calculator runs the cost-sharing waterfall
    3. If denied → Grievance Agent drafts an appeal letter
    4. Explanation Agent provides plain-English summary

    Requires a previously parsed PolicyProfile for accurate cost calculation.
    """
    graph = get_claim_evaluation_graph()

    try:
        safe_claim_description, _ = scrub_phi(request.claim_description)
    except PHIScrubbingError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    initial_state = {
        "messages": [],
        "raw_policy_text": "",
        "raw_claim_text": safe_claim_description,
        "benchmark_policy_excerpt": request.benchmark_policy_excerpt,
        "policy_profile": request.policy_profile,
        "claim_case": None,
        "allowed_amount": request.allowed_amount,
        "cost_breakdown": None,
        "appeal_output": None,
        "current_phase": "intake",
        "route_decision": "",
        "errors": [],
        "extraction_warnings": [],
        "extraction_confidence": None,
        "explanations": {},
        "session_id": request.session_id,
        "policy_indexed": request.policy_indexed,
    }

    try:
        result = await graph.ainvoke(initial_state)

        # Get the most relevant explanation
        explanations = result.get("explanations", {})
        explanation = explanations.get("appeal") or explanations.get("calculation") or explanations.get("intake")

        response = ClaimEvaluationResponse(
            success=bool(result.get("claim_case")),
            claim_case=result.get("claim_case"),
            cost_breakdown=result.get("cost_breakdown"),
            appeal_output=result.get("appeal_output"),
            explanation=explanation,
            route_decision=result.get("route_decision"),
            errors=result.get("errors", []),
        )

        if response.success:
            try:
                create_user_claim(
                    user_id=user["id"],
                    claim_description=safe_claim_description,
                    cost_breakdown=response.cost_breakdown,
                    appeal_output=response.appeal_output,
                    route_decision=response.route_decision,
                )
            except Exception:
                logger.error("Failed to save claim evaluation to Supabase", exc_info=True)
                response.errors = response.errors + [
                    "Claim evaluated, but it could not be saved to your history. Download or copy the result before leaving this page."
                ]

        return response

    except HTTPException:
        raise
    except Exception:
        logger.error("Claim evaluation failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Claim evaluation failed. Please try again.")
