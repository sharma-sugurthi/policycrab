from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import logging

from app.api.auth import get_current_user
from app.engine.carrier_directory import find_carrier, CARRIER_DIRECTORY, CarrierProfile
from app.engine.regulatory_router import get_appeal_framework_details, get_state_enriched_context
from app.models.enums import AppealFramework, PlanLegalClassification
from app.models.policy import PolicyProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/carrier", tags=["Carrier Routing"])


class RoutingRequest(BaseModel):
    carrier_name: str
    state: str
    framework: str = Field(..., description="The AppealFramework string value")


@router.get("/lookup")
async def lookup_carrier(q: str, _: dict = Depends(get_current_user)):
    """Find a carrier by name (fuzzy match)."""
    carrier = find_carrier(q)
    if not carrier:
        raise HTTPException(status_code=404, detail="Carrier not found in directory")
    return {"success": True, "carrier": carrier.__dict__}


@router.get("/all")
async def list_all_carriers(_: dict = Depends(get_current_user)):
    """List all supported carriers."""
    return {
        "success": True,
        "carriers": [c.__dict__ for c in CARRIER_DIRECTORY.values()]
    }


@router.post("/routing")
async def get_routing_package(req: RoutingRequest, _: dict = Depends(get_current_user)):
    """
    Get the complete routing package:
    1. Carrier submission address
    2. State DOI external review info
    3. Legal framework context
    """
    try:
        framework_enum = AppealFramework(req.framework)
    except ValueError:
        framework_enum = AppealFramework.STATE_DOI_COMPLAINT

    carrier = find_carrier(req.carrier_name)
    
    # We can use a dummy policy to get the state enriched context
    # Only plan_name, carrier_name, state are required string fields, others have defaults or can be omitted if optional, wait!
    # Let's check PolicyProfile required fields: plan_name, carrier_name, state
    dummy_policy = PolicyProfile(
        plan_name="Dummy Plan",
        carrier_name=req.carrier_name,
        state=req.state,
    )
    
    state_context = get_state_enriched_context(dummy_policy, framework_enum)
    framework_details = get_appeal_framework_details(framework_enum)
    
    return {
        "success": True,
        "carrier": carrier.__dict__ if carrier else None,
        "state_context": state_context,
        "framework_details": framework_details,
    }
