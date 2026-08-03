import logging
from typing import Any

logger = logging.getLogger(__name__)

def validate_eob_math(data: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministically validate medical billing math extracted by LLMs.
    Medical AI has zero tolerance for hallucinated numbers.
    If the math doesn't add up, we flag it so the Human-in-the-Loop can review.
    """
    if not isinstance(data, dict):
        return data

    errors = []
    
    # 1. Top-Level Validation
    billed = data.get("billed_amount")
    allowed = data.get("allowed_amount")
    plan_paid = data.get("plan_paid_amount")
    patient_resp = data.get("patient_responsibility")
    
    if isinstance(billed, (int, float)) and isinstance(allowed, (int, float)):
        if allowed > billed:
            errors.append(f"Top-level: Allowed Amount (${allowed}) cannot be greater than Billed Amount (${billed}).")
            
    if isinstance(allowed, (int, float)) and isinstance(plan_paid, (int, float)) and isinstance(patient_resp, (int, float)):
        # Allow $1.00 margin of error for rounding
        if abs((plan_paid + patient_resp) - allowed) > 1.0:
            errors.append(f"Top-level: Plan Paid (${plan_paid}) + Patient Resp (${patient_resp}) does not equal Allowed Amount (${allowed}).")

    # 2. Service Line Validation
    service_lines = data.get("service_lines", [])
    if isinstance(service_lines, list):
        for idx, line in enumerate(service_lines):
            if not isinstance(line, dict):
                continue
                
            l_billed = line.get("billed_amount")
            l_allowed = line.get("allowed_amount")
            l_plan_paid = line.get("plan_paid_amount")
            l_patient_resp = line.get("patient_responsibility")
            
            if isinstance(l_billed, (int, float)) and isinstance(l_allowed, (int, float)):
                if l_allowed > l_billed:
                    errors.append(f"Line {idx+1}: Allowed Amount (${l_allowed}) cannot be greater than Billed Amount (${l_billed}).")
                    
            if isinstance(l_allowed, (int, float)) and isinstance(l_plan_paid, (int, float)) and isinstance(l_patient_resp, (int, float)):
                if abs((l_plan_paid + l_patient_resp) - l_allowed) > 1.0:
                    errors.append(f"Line {idx+1}: Plan Paid (${l_plan_paid}) + Patient Resp (${l_patient_resp}) does not equal Allowed Amount (${l_allowed}).")

    # Inject errors array if any
    data["validation_errors"] = errors
    if errors:
        logger.warning(f"Math Validator caught {len(errors)} potential hallucinations: {errors}")
        
    return data
