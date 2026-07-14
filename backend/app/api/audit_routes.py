import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.auth import get_current_user
from app.security.rate_limit import rate_limit_user
from app.agents.bill_auditor import run_bill_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["Audit"])

class AuditRequest(BaseModel):
    cpt_code: Optional[str] = None
    cpt_description: Optional[str] = None
    icd_10_code: Optional[str] = None
    date_of_service: Optional[str] = None
    billed_amount: Optional[float] = None
    provider_name: Optional[str] = None
    facility_name: Optional[str] = None
    denial_reason_text: Optional[str] = None

# Per-user: 20 audits per hour
AUDIT_RATE_LIMIT = rate_limit_user("audit:scan", max_requests=20, window_seconds=3600)

@router.post("/scan")
async def scan_bill(
    request: AuditRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(AUDIT_RATE_LIMIT)
):
    """
    Scan claim data for potential billing errors, upcoding, or unbundling.
    """
    logger.info(f"Running bill audit for user {user.get('id')}")
    
    try:
        result = run_bill_audit(request.model_dump())
        return {"success": True, "audit_result": result}
    except Exception as e:
        logger.error(f"Audit endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to run bill audit.")
