import logging
import json
from pydantic import BaseModel, Field
from typing import List, Optional
from langchain_core.prompts import PromptTemplate
from app.services.llm_router import get_llm, TaskType

logger = logging.getLogger(__name__)

AUDIT_PROMPT = """You are a medical billing auditor and certified medical coder (CPC). 
Your job is to review the following claim details and flag potential billing errors, upcoding, unbundling, or excessive charges.

Claim Details:
- CPT Code: {cpt_code}
- CPT Description: {cpt_description}
- ICD-10 Code: {icd_10_code}
- Date of Service: {date_of_service}
- Billed Amount: {billed_amount}
- Provider/Facility: {provider_name}
- Denial Reason (if any): {denial_reason_text}

Rules for Auditing:
1. Upcoding: Check if the CPT code represents a high-level service (e.g., 99285, 99215) but lacks a severe diagnosis (ICD-10) to support it.
2. Unbundling: If multiple CPT codes were provided (or if the description implies multiple procedures), check if they should be bundled into a single comprehensive code.
3. Excessive Charges: Flag if the billed amount seems astronomically high for the service described.
4. Denial Context: If the claim is already denied, evaluate if the denial reason points to a coding error.

Return a JSON object matching this exact schema:
{{
  "risk_score": "Red" | "Yellow" | "Green",
  "summary": "Short 1-2 sentence summary of the audit finding.",
  "flags": [
    {{
      "issue_type": "Upcoding" | "Unbundling" | "Excessive Charge" | "Coding Error" | "General Warning",
      "description": "Detailed explanation of the issue.",
      "recommendation": "What the patient should do (e.g., 'Request an itemized bill', 'Ask provider for a coding review')."
    }}
  ]
}}

If there are no apparent issues, return "Green" with an empty flags list.
Return ONLY the JSON object. No explanation, no markdown fences."""

def run_bill_audit(claim_data: dict, llm=None) -> dict:
    """Run an LLM-based audit on claim data."""
    if not llm:
        llm = get_llm(TaskType.REASONING)
        
    prompt = PromptTemplate(
        template=AUDIT_PROMPT,
        input_variables=[
            "cpt_code", "cpt_description", "icd_10_code", 
            "date_of_service", "billed_amount", "provider_name", 
            "denial_reason_text"
        ]
    )
    
    # Fill in missing fields with "Not provided"
    safe_data = {
        "cpt_code": claim_data.get("cpt_code") or "Not provided",
        "cpt_description": claim_data.get("cpt_description") or "Not provided",
        "icd_10_code": claim_data.get("icd_10_code") or "Not provided",
        "date_of_service": claim_data.get("date_of_service") or "Not provided",
        "billed_amount": claim_data.get("billed_amount") or "Not provided",
        "provider_name": claim_data.get("provider_name") or claim_data.get("facility_name") or "Not provided",
        "denial_reason_text": claim_data.get("denial_reason_text") or "None"
    }

    try:
        chain = prompt | llm
        response_text = chain.invoke(safe_data).content
        
        # Clean markdown if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        result = json.loads(response_text.strip())
        return result
    except Exception as e:
        logger.error(f"Bill audit agent error: {e}")
        return {
            "risk_score": "Yellow",
            "summary": "Could not complete full automated audit due to an error.",
            "flags": [{
                "issue_type": "General Warning",
                "description": f"Audit failed: {str(e)}",
                "recommendation": "Review the bill manually."
            }]
        }
