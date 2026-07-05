"""
Claim API Routes — evaluate claims and calculate costs.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.agents.graph import get_claim_evaluation_graph
from app.api.auth import get_current_user

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
async def evaluate_claim(request: ClaimEvaluationRequest, user: dict = Depends(get_current_user)):
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

    initial_state = {
        "messages": [],
        "raw_policy_text": "",
        "raw_claim_text": request.claim_description,
        "policy_profile": request.policy_profile,
        "claim_case": None,
        "cost_breakdown": None,
        "appeal_output": None,
        "current_phase": "intake",
        "route_decision": "",
        "errors": [],
        "explanations": {},
    }

    try:
        result = await graph.ainvoke(initial_state)

        # Get the most relevant explanation
        explanations = result.get("explanations", {})
        explanation = explanations.get("appeal") or explanations.get("calculation") or explanations.get("intake")

        return ClaimEvaluationResponse(
            success=bool(result.get("claim_case")),
            claim_case=result.get("claim_case"),
            cost_breakdown=result.get("cost_breakdown"),
            appeal_output=result.get("appeal_output"),
            explanation=explanation,
            route_decision=result.get("route_decision"),
            errors=result.get("errors", []),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claim evaluation failed: {str(e)}")
