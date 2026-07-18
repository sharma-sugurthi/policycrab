"""
EOB Extractor Agent — single-step LLM extraction for Explanation of Benefits documents.

NOTE (Phase 2): This module is now the FALLBACK path only.
The PRIMARY extraction path is Gemini Multimodal in pdf_extractor.py,
which passes raw document bytes directly to Gemini for visual table understanding.

This text-based extractor is used when:
  - The Gemini Multimodal API is unavailable or fails.
  - A digital-text PDF was successfully parsed by PyMuPDF.
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ── Fallback LLM Text-to-JSON Extraction Prompt ──────────────────
# Schema MUST match the Gemini Multimodal schema in pdf_extractor.py
# so that both extraction paths produce identical output structures.
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
- document_type: classify as "eob", "bill", "policy", or "unknown".
- network_status: "IN_NETWORK" or "OUT_OF_NETWORK" or null
- facility_network_status: the HOSPITAL/FACILITY network status (may differ from the individual provider)
- ancillary_service_type: if the provider is anesthesiology, radiology, pathology, neonatology,
  or assistant surgeon, return the specialty name (e.g. "anesthesia", "radiology"). Otherwise null.

Return a single JSON object with this exact schema:
{{
  "document_type": "eob|bill|policy|unknown",
  "patient_name": "string or null",
  "claim_id": "string or null",
  "date_of_service": "YYYY-MM-DD or null",
  "denial_date": "YYYY-MM-DD or null",
  "billed_amount": float or null,
  "allowed_amount": float or null,
  "plan_paid_amount": float or null,
  "patient_responsibility": float or null,
  "provider_name": "string or null",
  "facility_name": "string or null",
  "network_status": "IN_NETWORK|OUT_OF_NETWORK or null",
  "facility_network_status": "IN_NETWORK|OUT_OF_NETWORK or null",
  "ancillary_service_type": "anesthesia|radiology|pathology|neonatology or null",
  "cpt_code": "string or null",
  "cpt_description": "string or null",
  "icd_10_code": "string or null",
  "icd_10_description": "string or null",
  "denial_carc_code": "string or null",
  "denial_rarc_code": "string or null",
  "denial_reason_text": "string or null — verbatim denial reason from the EOB",
  "is_denied": true or false,
  "service_lines": [
    {{
      "provider_name": "string or null",
      "network_status": "IN_NETWORK|OUT_OF_NETWORK or null",
      "ancillary_service_type": "string or null",
      "cpt_code": "string or null",
      "cpt_description": "string or null",
      "billed_amount": float or null,
      "allowed_amount": float or null,
      "plan_paid_amount": float or null,
      "patient_responsibility": float or null,
      "denial_carc_code": "string or null",
      "denial_reason_text": "string or null"
    }}
  ],
  "confidence": {{
    "date_of_service": "high|medium|low",
    "billed_amount": "high|medium|low",
    "allowed_amount": "high|medium|low",
    "cpt_code": "high|medium|low",
    "denial_carc_code": "high|medium|low",
    "network_status": "high|medium|low",
    "facility_network_status": "high|medium|low"
  }}
}}

DOCUMENT TEXT:
\"\"\"
{eob_text}
\"\"\"

Return ONLY the JSON object. No explanation, no markdown fences."""


def extract_eob_fields(eob_text: str, llm: Any) -> dict:
    """
    Run single-step LLM extraction on EOB document text.

    This is the FALLBACK path used when Gemini Multimodal is unavailable.
    The primary path (Gemini Multimodal) is in pdf_extractor.py.

    Returns the parsed EOB extraction dict matching the schema above.
    """
    prompt = EOB_EXTRACTION_PROMPT.format(eob_text=eob_text[:6000])

    logger.info(
        f"EOB Extractor (text fallback): Running extraction on "
        f"{len(eob_text)} chars of EOB text"
    )

    try:
        response = llm.invoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)

        # Strip markdown fences if LLM wrapped the JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        result = json.loads(raw)
        logger.info(
            f"EOB Extractor (fallback): Successfully extracted fields. "
            f"Denied={result.get('is_denied')}, "
            f"facility_network_status={result.get('facility_network_status')}, "
            f"ancillary={result.get('ancillary_service_type')}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"EOB Extractor: Failed to parse LLM response as JSON: {e}")
        return {"error": f"Failed to parse response: {e}", "raw": raw[:500]}
    except Exception as e:
        logger.error(f"EOB Extractor: Extraction failed: {e}")
        return {"error": str(e)}
