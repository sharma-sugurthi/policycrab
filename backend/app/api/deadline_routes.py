import logging
from datetime import date
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.services.supabase_client import get_supabase_client
from app.services.llm_router import get_llm, TaskType
from app.engine.regulatory_router import get_state_enriched_context
from app.models.policy import PolicyProfile
from app.models.enums import AppealFramework

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deadlines", tags=["Deadlines"])


class DeadlineCreate(BaseModel):
    carrier_name: str
    appeal_level: str
    appeal_framework: str
    state_code: str
    date_denial_received: date
    date_appeal_filed: date | None = None
    deadline_date: date
    statutory_days: int
    insurer_response_deadline: date | None = None
    insurer_response_days: int | None = None
    notes: str | None = None
    claim_summary: str | None = None


class DeadlineUpdate(BaseModel):
    date_appeal_filed: date | None = None
    insurer_response_deadline: date | None = None
    status: str | None = None
    notes: str | None = None


@router.get("")
async def get_deadlines(user: dict = Depends(get_current_user)):
    """Get all deadlines for the current user."""
    client = get_supabase_client()
    try:
        result = client.table("appeal_deadlines").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
        return {"success": True, "deadlines": result.data or []}
    except Exception as e:
        logger.error(f"Error fetching deadlines: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch deadlines")


@router.post("")
async def create_deadline(req: DeadlineCreate, user: dict = Depends(get_current_user)):
    """Create a new deadline tracker."""
    client = get_supabase_client()
    data = req.model_dump(mode="json")
    data["user_id"] = user["id"]
    try:
        result = client.table("appeal_deadlines").insert(data).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return {"success": True, "deadline": result.data[0]}
    except Exception as e:
        logger.error(f"Error creating deadline: {e}")
        raise HTTPException(status_code=500, detail="Failed to create deadline")


@router.patch("/{deadline_id}")
async def update_deadline(deadline_id: str, req: DeadlineUpdate, user: dict = Depends(get_current_user)):
    """Update a deadline (e.g., mark as filed, change status)."""
    client = get_supabase_client()
    data = req.model_dump(exclude_unset=True, mode="json")
    if not data:
        return {"success": True}
        
    try:
        # RLS ensures they can only update their own
        result = client.table("appeal_deadlines").update(data).eq("id", deadline_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Deadline not found")
        return {"success": True, "deadline": result.data[0]}
    except Exception as e:
        logger.error(f"Error updating deadline: {e}")
        raise HTTPException(status_code=500, detail="Failed to update deadline")


@router.delete("/{deadline_id}")
async def delete_deadline(deadline_id: str, user: dict = Depends(get_current_user)):
    """Delete a deadline."""
    client = get_supabase_client()
    try:
        result = client.table("appeal_deadlines").delete().eq("id", deadline_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Deadline not found")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error deleting deadline: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete deadline")


@router.post("/{deadline_id}/breach-letter")
async def generate_breach_letter(deadline_id: str, user: dict = Depends(get_current_user)):
    """Generate a formal DOI complaint letter for an overdue insurer response."""
    client = get_supabase_client()
    try:
        result = client.table("appeal_deadlines").select("*").eq("id", deadline_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Deadline not found")
        deadline = result.data[0]
    except Exception as e:
        logger.error(f"Error fetching deadline for breach letter: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch deadline")

    # Ensure it's actually breached
    if not deadline.get("insurer_response_deadline"):
        raise HTTPException(status_code=400, detail="No response deadline set. Mark appeal as filed first.")

    today = date.today()
    response_deadline = date.fromisoformat(deadline["insurer_response_deadline"])
    days_overdue = (today - response_deadline).days

    if days_overdue <= 0:
        raise HTTPException(status_code=400, detail="Deadline has not been breached yet.")

    # Get state regulatory context
    try:
        framework = AppealFramework(deadline["appeal_framework"])
    except ValueError:
        framework = AppealFramework.STATE_DOI_COMPLAINT

    dummy_policy = PolicyProfile(
        plan_name="Member Plan",
        carrier_name=deadline["carrier_name"],
        state=deadline["state_code"]
    )
    state_ctx = get_state_enriched_context(dummy_policy, framework)

    llm = get_llm(TaskType.LEGAL_WRITING)
    
    prompt = f"""
    You are an expert healthcare advocate drafting a formal regulatory complaint.
    The health insurer has breached statutory deadlines for responding to an appeal.
    
    INSURER: {deadline['carrier_name']}
    STATE: {deadline['state_code']}
    DAYS OVERDUE: {days_overdue} days (Deadline was {response_deadline.isoformat()})
    APPEAL LEVEL: {deadline['appeal_level']}
    FRAMEWORK: {deadline['appeal_framework']}
    CLAIM SUMMARY: {deadline['claim_summary'] or "A submitted healthcare claim"}
    
    STATE PROTECTIONS OVERVIEW:
    {state_ctx}
    
    INSTRUCTIONS:
    Write a formal complaint letter addressed to the State Department of Insurance (or appropriate federal body if ERISA).
    1. Clearly state that the insurer has missed their statutory response deadline by {days_overdue} days.
    2. Demand immediate resolution of the appeal.
    3. Request the regulatory body to investigate this delay as a potential violation of prompt payment or claims settlement laws.
    4. Keep the tone professional, firm, and legally precise.
    5. Do not include placeholders like "[Your Name]" — instead use clear marker like "MEMBER NAME:" for them to fill in later. Just output the letter text. No introductory or concluding remarks.
    """

    try:
        response = await llm.ainvoke(prompt)
        letter = response.content.strip()
        return {"success": True, "letter": letter, "days_overdue": days_overdue}
    except Exception as e:
        logger.error(f"LLM breach letter generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate breach letter")
