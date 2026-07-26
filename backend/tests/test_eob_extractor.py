"""
Tests for the EOB Extractor Agent (eob_extractor.py).

All LLM calls are mocked — these tests run entirely offline.

Covers:
- Valid EOB → correct structured dict returned
- Null-safe: missing fields returned as null, not guessed
- NSA-critical fields parsed correctly (facility_network_status, ancillary_service_type)
- Markdown fences stripped before JSON parsing
- Malformed JSON handled gracefully (returns error dict, not exception)
- CARC code extraction from a denial EOB
"""

import json
import pytest
from unittest.mock import MagicMock


# ── Mock LLM factory ──────────────────────────────────────────────

def _make_sync_llm(content: str):
    """Return a synchronous mock LLM (eob_extractor uses llm.invoke, not ainvoke)."""
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return mock_llm


# ── EOB response fixtures ─────────────────────────────────────────

FULL_VALID_EOB = json.dumps({
    "document_type": "eob",
    "patient_name": "Jane Doe",
    "claim_id": "CLM-2025-001",
    "date_of_service": "2025-06-15",
    "denial_date": None,
    "billed_amount": 4500.0,
    "allowed_amount": 3200.0,
    "plan_paid_amount": 2560.0,
    "patient_responsibility": 640.0,
    "provider_name": "Dr. Smith",
    "facility_name": "Cedars-Sinai Medical Center",
    "network_status": "IN_NETWORK",
    "facility_network_status": "IN_NETWORK",
    "ancillary_service_type": None,
    "cpt_code": "27447",
    "cpt_description": "Total Knee Replacement",
    "icd_10_code": "M17.11",
    "icd_10_description": "Primary osteoarthritis, right knee",
    "denial_carc_code": None,
    "denial_rarc_code": None,
    "denial_reason_text": None,
    "is_denied": False,
    "service_lines": [],
    "confidence": {
        "date_of_service": "high",
        "billed_amount": "high",
        "allowed_amount": "high",
        "cpt_code": "high",
        "denial_carc_code": "high",
        "network_status": "high",
        "facility_network_status": "high",
    }
})

# NSA Scenario B: OON anesthesiologist at INN facility
NSA_SCENARIO_B_EOB = json.dumps({
    "document_type": "eob",
    "patient_name": "John Patient",
    "claim_id": "CLM-2025-NSA-001",
    "date_of_service": "2025-07-01",
    "denial_date": "2025-07-20",
    "billed_amount": 5200.0,
    "allowed_amount": 400.0,
    "plan_paid_amount": 0.0,
    "patient_responsibility": 5200.0,
    "provider_name": "Apex Anesthesia Associates",
    "facility_name": "St. Jude Medical Center",
    "network_status": "OUT_OF_NETWORK",
    "facility_network_status": "IN_NETWORK",
    "ancillary_service_type": "anesthesia",
    "cpt_code": "00790",
    "cpt_description": "Anesthesia for abdominal surgery",
    "icd_10_code": "K80.20",
    "icd_10_description": "Calculus of gallbladder without cholecystitis",
    "denial_carc_code": "CO-45",
    "denial_rarc_code": "N115",
    "denial_reason_text": "Charge exceeds maximum allowable fee schedule",
    "is_denied": True,
    "service_lines": [],
    "confidence": {
        "date_of_service": "high",
        "billed_amount": "high",
        "allowed_amount": "high",
        "cpt_code": "high",
        "denial_carc_code": "high",
        "network_status": "high",
        "facility_network_status": "high",
    }
})

MISSING_MODIFIER_EOB = json.dumps({
    "document_type": "eob",
    "patient_name": None,
    "claim_id": "CLM-2025-CO4",
    "date_of_service": "2025-05-10",
    "denial_date": "2025-05-28",
    "billed_amount": 350.0,
    "allowed_amount": None,
    "plan_paid_amount": 0.0,
    "patient_responsibility": 350.0,
    "provider_name": "City Medical Group",
    "facility_name": None,
    "network_status": "IN_NETWORK",
    "facility_network_status": None,
    "ancillary_service_type": None,
    "cpt_code": "99213",
    "cpt_description": "Office or other outpatient visit",
    "icd_10_code": "J06.9",
    "icd_10_description": "Acute upper respiratory infection",
    "denial_carc_code": "CO-4",
    "denial_rarc_code": "M51",
    "denial_reason_text": "Modifier is missing, incorrect, or does not apply",
    "is_denied": True,
    "service_lines": [],
    "confidence": {
        "date_of_service": "high",
        "billed_amount": "high",
        "allowed_amount": "low",
        "cpt_code": "high",
        "denial_carc_code": "high",
        "network_status": "high",
        "facility_network_status": "low",
    }
})


# ── Test Suite ────────────────────────────────────────────────────

class TestEOBExtractorValidData:
    """Standard valid EOB documents are parsed into complete structured dicts."""

    def test_valid_eob_returns_correct_structure(self):
        """A complete EOB response must be parsed into the expected fields."""
        from app.agents.eob_extractor import extract_eob_fields

        result = extract_eob_fields("Full EOB text here", _make_sync_llm(FULL_VALID_EOB))

        assert result.get("document_type") == "eob"
        assert result.get("billed_amount") == 4500.0
        assert result.get("allowed_amount") == 3200.0
        assert result.get("is_denied") is False
        assert result.get("network_status") == "IN_NETWORK"

    def test_valid_eob_no_error_key(self):
        """A successful extraction must NOT have an 'error' key."""
        from app.agents.eob_extractor import extract_eob_fields

        result = extract_eob_fields("EOB text", _make_sync_llm(FULL_VALID_EOB))

        assert "error" not in result

    def test_valid_eob_cpt_and_icd_codes_extracted(self):
        """CPT and ICD-10 codes must be extracted verbatim."""
        from app.agents.eob_extractor import extract_eob_fields

        result = extract_eob_fields("EOB text", _make_sync_llm(FULL_VALID_EOB))

        assert result.get("cpt_code") == "27447"
        assert result.get("icd_10_code") == "M17.11"


class TestEOBExtractorNSAFields:
    """NSA-critical fields (facility_network_status, ancillary_service_type) must parse correctly."""

    def test_nsa_scenario_b_fields_extracted(self):
        """
        NSA Scenario B: OON ancillary provider at INN facility.
        Both facility_network_status and ancillary_service_type must be set.
        """
        from app.agents.eob_extractor import extract_eob_fields

        result = extract_eob_fields("NSA EOB text", _make_sync_llm(NSA_SCENARIO_B_EOB))

        assert result.get("network_status") == "OUT_OF_NETWORK"
        assert result.get("facility_network_status") == "IN_NETWORK"
        assert result.get("ancillary_service_type") == "anesthesia"

    def test_nsa_denial_flags_are_set(self):
        """An NSA balance bill scenario must show is_denied=True and a CARC code."""
        from app.agents.eob_extractor import extract_eob_fields

        result = extract_eob_fields("NSA EOB text", _make_sync_llm(NSA_SCENARIO_B_EOB))

        assert result.get("is_denied") is True
        assert result.get("denial_carc_code") == "CO-45"

    def test_null_facility_network_status_preserved(self):
        """
        When facility_network_status is not in the document, it must be null.
        This is the Phase 1 anti-hallucination guarantee for EOB extraction too.
        """
        from app.agents.eob_extractor import extract_eob_fields

        result = extract_eob_fields("CO-4 EOB text", _make_sync_llm(MISSING_MODIFIER_EOB))

        assert result.get("facility_network_status") is None


class TestEOBExtractorCARCCodes:
    """Denial CARC codes must be parsed and surfaced correctly."""

    def test_carc_co4_extracted_from_denial(self):
        """CO-4 (missing modifier) denial must be extracted with exact code."""
        from app.agents.eob_extractor import extract_eob_fields

        result = extract_eob_fields("Missing modifier EOB", _make_sync_llm(MISSING_MODIFIER_EOB))

        assert result.get("is_denied") is True
        assert result.get("denial_carc_code") == "CO-4"
        assert result.get("denial_rarc_code") == "M51"
        assert "modifier" in result.get("denial_reason_text", "").lower()

    def test_null_carc_preserved_when_not_denied(self):
        """For approved claims, denial_carc_code must be null, not fabricated."""
        from app.agents.eob_extractor import extract_eob_fields

        result = extract_eob_fields("Approved EOB", _make_sync_llm(FULL_VALID_EOB))

        assert result.get("denial_carc_code") is None
        assert result.get("is_denied") is False


class TestEOBExtractorMarkdownStripping:
    """LLMs sometimes wrap JSON in markdown fences — these must be stripped."""

    def test_markdown_json_fence_stripped(self):
        """JSON wrapped in ```json ... ``` fences must parse correctly."""
        from app.agents.eob_extractor import extract_eob_fields

        wrapped = f"```json\n{FULL_VALID_EOB}\n```"
        result = extract_eob_fields("EOB text", _make_sync_llm(wrapped))

        assert result.get("billed_amount") == 4500.0
        assert "error" not in result

    def test_plain_markdown_fence_stripped(self):
        """JSON wrapped in plain ``` ... ``` fences must also parse correctly."""
        from app.agents.eob_extractor import extract_eob_fields

        wrapped = f"```\n{FULL_VALID_EOB}\n```"
        result = extract_eob_fields("EOB text", _make_sync_llm(wrapped))

        assert result.get("is_denied") is False
        assert "error" not in result


class TestEOBExtractorErrorHandling:
    """Malformed or garbled LLM output must not crash the agent."""

    def test_garbled_response_returns_error_dict(self):
        """
        If the LLM returns non-JSON text, the function must return a dict
        with an 'error' key — NOT raise an unhandled exception.
        """
        from app.agents.eob_extractor import extract_eob_fields

        garbled = "I cannot extract this document. Please try again with a clearer image."
        result = extract_eob_fields("EOB text", _make_sync_llm(garbled))

        assert "error" in result

    def test_empty_response_returns_error_dict(self):
        """An empty LLM response must return an error dict, not crash."""
        from app.agents.eob_extractor import extract_eob_fields

        result = extract_eob_fields("EOB text", _make_sync_llm(""))

        assert "error" in result

    def test_partial_json_returns_error_dict(self):
        """Truncated JSON must return an error dict, not a silent partial parse."""
        from app.agents.eob_extractor import extract_eob_fields

        truncated = '{"document_type": "eob", "billed_amount": 1200.0, "cpt_code"'
        result = extract_eob_fields("EOB text", _make_sync_llm(truncated))

        assert "error" in result


class TestEOBPostProcessing:
    def test_labeled_fields_are_recovered_and_patient_name_removed(self):
        from app.agents.eob_extractor import postprocess_eob_result

        text = (
            "Patient: Test Patient Member ID: TST123456789 "
            "Date of Service: 2026-06-15 Provider: Bay Imaging Center "
            "Facility: Bay Imaging Center Service: MRI right knee without contrast "
            "CPT Code: 73721 ICD-10 Code: M25.561 Billed Amount: $3,500.00 "
            "Allowed Amount: $1,200.00 Plan Paid: $0.00 "
            "Patient Responsibility: $1,200.00 Claim Status: Denied "
            "Denial Reason: CO-50 These services are not deemed medically necessary by the payer. "
            "Denial Date: 2026-07-01 Appeal Deadline: 180 days from denial notice."
        )
        result = postprocess_eob_result({
            "patient_name": "Test Patient",
            "document_type": "eob",
            "denial_reason_text": "Denied",
            "service_lines": [{"denial_reason_text": "Denied"}],
        }, text)

        assert result["patient_name"] is None
        assert result["provider_name"] == "Bay Imaging Center"
        assert result["facility_name"] == "Bay Imaging Center"
        assert result["date_of_service"] == "2026-06-15"
        assert result["denial_date"] == "2026-07-01"
        assert result["cpt_code"] == "73721"
        assert result["icd_10_code"] == "M25.561"
        assert result["denial_carc_code"] == "CO-50"
        assert "medically necessary" in result["denial_reason_text"]
        assert result["service_lines"][0]["denial_carc_code"] == "CO-50"
