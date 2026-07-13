from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.services.user_data import list_user_claims, list_user_policies

router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("/policies")
async def get_user_policies(user: dict = Depends(get_current_user)):
    """Get all policies uploaded by the current user."""
    return [
        {
            "id": policy["id"],
            "policy_profile": policy.get("policy_profile_json"),
            "created_at": policy.get("created_at"),
        }
        for policy in list_user_policies(user["id"])
    ]


@router.get("/claims")
async def get_user_claims(user: dict = Depends(get_current_user)):
    """Get all claim evaluations run by the current user."""
    return [
        {
            "id": claim["id"],
            "claim_description": claim.get("claim_description"),
            "cost_breakdown": claim.get("cost_breakdown_json"),
            "appeal_output": claim.get("appeal_output_json"),
            "route_decision": claim.get("route_decision"),
            "created_at": claim.get("created_at"),
        }
        for claim in list_user_claims(user["id"])
    ]
