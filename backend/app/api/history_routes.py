from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from app.api.auth import get_current_user
from app.database import get_db
from app.models.db_models import UserPolicy, UserClaim

router = APIRouter(prefix="/api/history", tags=["History"])

@router.get("/policies")
async def get_user_policies(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all policies uploaded by the current user."""
    stmt = select(UserPolicy).where(UserPolicy.user_id == user["id"]).order_by(desc(UserPolicy.created_at))
    result = await db.execute(stmt)
    policies = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "policy_profile": p.policy_profile_json,
            "created_at": p.created_at
        }
        for p in policies
    ]

@router.get("/claims")
async def get_user_claims(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all claim evaluations run by the current user."""
    stmt = select(UserClaim).where(UserClaim.user_id == user["id"]).order_by(desc(UserClaim.created_at))
    result = await db.execute(stmt)
    claims = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "claim_description": c.claim_description,
            "cost_breakdown": c.cost_breakdown_json,
            "appeal_output": c.appeal_output_json,
            "route_decision": c.route_decision,
            "created_at": c.created_at
        }
        for c in claims
    ]
