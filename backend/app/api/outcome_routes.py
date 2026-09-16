"""
Outcome API — record what actually happened to an appeal and read calibration.

POST /api/outcomes                 record/upsert an outcome for one of my claims
GET  /api/outcomes                 list my recorded outcomes
GET  /api/outcomes/calibration     predicted-vs-observed table for my claims
GET  /api/outcomes/calibration?scope=global   platform-wide (admin allowlist only)
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.services.audit_trail import record_audit
from app.api.admin_routes import require_admin
from app.security.rate_limit import rate_limit_user
from app.services.outcomes import (
    VALID_OUTCOMES,
    record_outcome,
    list_outcomes,
    fetch_outcomes_for_calibration,
    compute_calibration,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/outcomes", tags=["Outcomes"])

# Per-user: 30 outcome writes per hour
OUTCOME_WRITE_RATE_LIMIT = rate_limit_user("outcomes:write", max_requests=30, window_seconds=3600)


class OutcomeCreate(BaseModel):
    claim_id: str = Field(..., min_length=8, description="user_claims.id the outcome belongs to")
    outcome: str = Field(..., description="won | partial | lost | pending | withdrawn")
    amount_recovered: float | None = Field(None, ge=0)
    amount_at_stake: float | None = Field(None, ge=0)
    appeal_level: int | None = Field(None, ge=1, le=3)
    decided_at: date | None = None
    notes: str | None = Field(None, max_length=2000)


@router.post("", status_code=201)
async def create_outcome(
    body: OutcomeCreate,
    request: Request,
    user: dict = Depends(get_current_user),
    _: None = Depends(OUTCOME_WRITE_RATE_LIMIT),
):
    """Record (or update) the real-world outcome of one of your appeals."""
    if body.outcome.lower() not in VALID_OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of: {', '.join(VALID_OUTCOMES)}")
    try:
        saved = record_outcome(
            user_id=user["id"],
            claim_id=body.claim_id,
            payload={
                "outcome": body.outcome.lower(),
                "amount_recovered": body.amount_recovered,
                "amount_at_stake": body.amount_at_stake,
                "appeal_level": body.appeal_level,
                "decided_at": body.decided_at.isoformat() if body.decided_at else None,
                "notes": body.notes,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404 if "not found" in str(e).lower() else 422, detail=str(e))
    except Exception:
        logger.error("Failed to record appeal outcome", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save the outcome. Please try again.")
    record_audit("outcome.recorded", user_id=user["id"], resource_type="claim", resource_id=body.claim_id,
                 metadata={"outcome": body.outcome.lower(), "appeal_level": body.appeal_level}, request=request)
    return {"success": True, "outcome": saved}


@router.get("")
async def get_outcomes(user: dict = Depends(get_current_user)):
    """List the outcomes you have recorded."""
    return {"outcomes": list_outcomes(user["id"])}


@router.get("/calibration")
async def get_calibration(
    scope: str = Query("mine", pattern="^(mine|global)$"),
    user: dict = Depends(get_current_user),
):
    """
    Predicted-vs-observed calibration. `scope=global` aggregates every user and
    requires platform admin rights.
    """
    if scope == "global":
        require_admin(user)   # raises 403 for non-admins
        rows = fetch_outcomes_for_calibration(None)
    else:
        rows = fetch_outcomes_for_calibration(user["id"])
    return {"scope": scope, "calibration": compute_calibration(rows)}
