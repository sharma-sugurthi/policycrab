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
- Do not extract patient names. Always return patient_name as null.
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


def _label_value(text: str, label: str) -> str | None:
    labels = [
        "Patient", "Member ID", "Claim ID", "Date of Service", "Provider", "Facility",
        "Service", "CPT Code", "ICD-10 Code", "Billed Amount", "Allowed Amount",
        "Plan Paid", "Patient Responsibility", "Claim Status", "Denial Reason",
        "Denial Date", "Appeal Deadline", "Network Status", "Facility Network Status",
    ]
    other_labels = [re.escape(item) for item in labels if item.lower() != label.lower()]
    pattern = rf"(?is)\b{re.escape(label)}\s*:\s*(.*?)(?=\s+(?:{'|'.join(other_labels)})\s*:|\n|$)"
    match = re.search(pattern, text)
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip(" -\t\r\n")
    return value or None


def _amount_from_label(text: str, label: str) -> float | None:
    value = _label_value(text, label)
    if not value:
        return None
    match = re.search(r"\$?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", value)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def _iso_date_from_label(text: str, label: str) -> str | None:
    value = _label_value(text, label)
    if not value:
        return None
    iso = re.search(r"\b(20\d{2}|19\d{2})-(\d{2})-(\d{2})\b", value)
    if iso:
        return iso.group(0)
    us = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2}|19\d{2})\b", value)
    if us:
        month, day, year = us.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return None


def _first_code(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else None


def postprocess_eob_result(result: dict, document_text: str) -> dict:
    """Recover obvious labeled EOB fields and remove unnecessary patient identifiers."""
    if not isinstance(result, dict):
        return result

    result = dict(result)
    result["patient_name"] = None

    field_labels = {
        "date_of_service": ("Date of Service", _iso_date_from_label),
        "denial_date": ("Denial Date", _iso_date_from_label),
        "billed_amount": ("Billed Amount", _amount_from_label),
        "allowed_amount": ("Allowed Amount", _amount_from_label),
        "plan_paid_amount": ("Plan Paid", _amount_from_label),
        "patient_responsibility": ("Patient Responsibility", _amount_from_label),
        "provider_name": ("Provider", _label_value),
        "facility_name": ("Facility", _label_value),
        "cpt_description": ("Service", _label_value),
    }

    for field, (label, extractor) in field_labels.items():
        recovered = extractor(document_text, label)
        if recovered is not None and (result.get(field) in (None, "", "Denied")):
            result[field] = recovered

    cpt = _first_code(document_text, r"\bCPT(?:\s+Code)?\s*:\s*([A-Z]?\d{4,5})\b")
    if cpt and not result.get("cpt_code"):
        result["cpt_code"] = cpt

    icd = _first_code(document_text, r"\bICD-?10(?:\s+Code)?\s*:\s*([A-Z]\d{2}(?:\.\d+)?)\b")
    if icd and not result.get("icd_10_code"):
        result["icd_10_code"] = icd

    denial_text = _label_value(document_text, "Denial Reason")
    if denial_text:
        carc = _first_code(denial_text, r"\b((?:CO|PR|OA|PI)-\d{1,3})\b")
        if carc and not result.get("denial_carc_code"):
            result["denial_carc_code"] = carc
        if result.get("denial_reason_text") in (None, "", "Denied") or len(str(result.get("denial_reason_text"))) < len(denial_text):
            result["denial_reason_text"] = denial_text
        result["is_denied"] = True

    service_lines = result.get("service_lines")
    if isinstance(service_lines, list) and service_lines:
        first = dict(service_lines[0])
        for field in ("provider_name", "network_status", "ancillary_service_type", "cpt_code", "cpt_description", "billed_amount", "allowed_amount", "plan_paid_amount", "patient_responsibility", "denial_carc_code", "denial_reason_text"):
            if first.get(field) in (None, "", "Denied") and result.get(field) not in (None, ""):
                first[field] = result.get(field)
        service_lines[0] = first
        result["service_lines"] = service_lines

    return result


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

        result = postprocess_eob_result(json.loads(raw), eob_text)
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
