"""
EOB Extractor Agent — single-step LLM extraction for Explanation of Benefits documents.

Unlike the policy ingestion pipeline (which uses a full LangGraph state machine),
EOB extraction is a lightweight single-step operation: PDF text → structured JSON.
This keeps latency low and cost minimal for a common user action.
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


EOB_EXTRACTION_PROMPT = """You are a US health insurance specialist extracting structured data from a healthcare document.

The document could be an Explanation of Benefits (EOB), a medical bill/itemized statement, an insurance policy/SBC, or something else.

RULES:
- Extract ONLY what is explicitly stated in the document. Do NOT guess or hallucinate.
- For any field not found, return null.
- Dates must be in ISO format: YYYY-MM-DD
- Amounts must be numeric floats (no $ signs or commas)
- CARC codes follow pattern: CO-50, PR-96, OA-18, etc.
- RARC codes follow pattern: N115, M51, etc.
- CPT codes are 5-digit numeric or alphanumeric (e.g., 99285, 27447, J0129)
- ICD-10 codes follow pattern: A00.0, I21.0, M17.11, etc.
- document_type: classify as "eob" (Explanation of Benefits), "bill" (itemized medical bill/invoice), "policy" (insurance policy, SBC, or benefit summary), or "unknown".

Return a single JSON object with this exact schema:
{
  "document_type": "eob|bill|policy|unknown",
  "date_of_service": "YYYY-MM-DD or null",
  "denial_date": "YYYY-MM-DD or null",
  "billed_amount": float or null,
  "allowed_amount": float or null,
  "plan_paid_amount": float or null,
  "patient_responsibility": float or null,
  "provider_name": "string or null",
  "facility_name": "string or null",
  "cpt_code": "string or null",
  "cpt_description": "string or null",
  "icd_10_code": "string or null",
  "icd_10_description": "string or null",
  "denial_carc_code": "string or null",
  "denial_rarc_code": "string or null",
  "denial_reason_text": "string or null — verbatim denial reason from the EOB",
  "is_denied": true or false,
  "confidence": {
    "date_of_service": "high|medium|low",
    "billed_amount": "high|medium|low",
    "allowed_amount": "high|medium|low",
    "cpt_code": "high|medium|low",
    "denial_carc_code": "high|medium|low"
  }
}

DOCUMENT TEXT:
\"\"\"
{eob_text}
\"\"\"

Return ONLY the JSON object. No explanation, no markdown fences."""


def extract_eob_fields(eob_text: str, llm: Any) -> dict:
    """
    Run single-step LLM extraction on EOB document text.
    Returns the parsed EOBExtractResult dict.
    """
    prompt = EOB_EXTRACTION_PROMPT.format(eob_text=eob_text[:6000])

    logger.info(f"EOB Extractor: Running extraction on {len(eob_text)} chars of EOB text")

    try:
        response = llm.invoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)

        # Strip markdown fences if LLM wrapped the JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        result = json.loads(raw)
        logger.info(f"EOB Extractor: Successfully extracted fields. Denied={result.get('is_denied')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"EOB Extractor: Failed to parse LLM response as JSON: {e}")
        return {"error": f"Failed to parse response: {e}", "raw": raw[:500]}
    except Exception as e:
        logger.error(f"EOB Extractor: Extraction failed: {e}")
        return {"error": str(e)}
