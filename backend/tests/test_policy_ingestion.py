"""
Tests for the Policy Ingestion Agent (policy_ingestion.py).

All LLM calls and embedding API calls are mocked — these tests run
entirely offline and do NOT require API keys or a Supabase connection.

Covers:
- Phase 1 fix: null values are preserved (not fabricated)
- Extraction warnings are raised for missing critical fields
- Sanity checks catch out-of-range values when fields ARE present
- JSON parse errors are handled gracefully without crashing
- Pydantic validation rejects structurally invalid LLM output
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock


# ── Shared Mock Factories ─────────────────────────────────────────

def _make_llm(content: str):
    """Return a mock LLM whose ainvoke() returns the given string as content."""
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_response
    return mock_llm


def _make_embed_fn(return_value=None):
    """Return a mock embed function that skips the real API."""
    if return_value is None:
        return_value = [{"chunk_text": "fake", "embedding": [0.1] * 768,
                         "page_number": 1, "chunk_index": 0}]
    return AsyncMock(return_value=return_value)


def _make_insert_fn(inserted=1):
    """Return a mock insert function that simulates Supabase storage."""
    return AsyncMock(return_value=inserted)


# ── Valid LLM response fixtures ───────────────────────────────────

FULL_VALID_RESPONSE = json.dumps({
    "plan_name": "BlueCross PPO Gold",
    "carrier_name": "BlueCross BlueShield",
    "plan_type": "PPO",
    "legal_classification": "FULLY_INSURED",
    "state": "CA",
    "in_network_deductible_individual": 1500.0,
    "in_network_oop_max_individual": 6000.0,
    "in_network_coinsurance": 0.20,
    "out_of_network_deductible_individual": None,
    "out_of_network_oop_max_individual": None,
    "out_of_network_coinsurance": None,
    "copay_schedule": {
        "primary_care": 25.0,
        "specialist": 50.0,
        "urgent_care": 75.0,
        "emergency_room": 250.0,
    },
    "is_hsa_eligible": False,
    "requires_pcp_referral": False,
    "prior_auth_required_categories": ["elective surgery"],
    "excluded_services": [],
})

# SBC with missing deductible and OOP max — LLM correctly returns null
MISSING_DEDUCTIBLE_RESPONSE = json.dumps({
    "plan_name": "Acme HMO Silver",
    "carrier_name": "Acme Health",
    "plan_type": "HMO",
    "legal_classification": "FULLY_INSURED",
    "state": "NY",
    "in_network_deductible_individual": None,   # MISSING in document
    "in_network_oop_max_individual": None,       # MISSING in document
    "in_network_coinsurance": 0.20,
    "is_hsa_eligible": False,
    "requires_pcp_referral": True,
})

# LLM returns an out-of-range deductible
OUT_OF_RANGE_DEDUCTIBLE_RESPONSE = json.dumps({
    "plan_name": "Expensive Plan",
    "carrier_name": "BigCorp Insurance",
    "plan_type": "PPO",
    "legal_classification": "SELF_FUNDED_ERISA",
    "state": "TX",
    "in_network_deductible_individual": 99999.0,   # Way out of range
    "in_network_oop_max_individual": 8000.0,
    "in_network_coinsurance": 0.30,
    "is_hsa_eligible": False,
    "requires_pcp_referral": False,
})


# ── Test Suite ────────────────────────────────────────────────────

class TestPolicyIngestionNullHandling:
    """
    Phase 1 fix: When a field is missing in the SBC, the LLM returns null.
    The agent MUST preserve null rather than raise a Pydantic error.
    """

    @pytest.mark.asyncio
    async def test_null_deductible_is_preserved_not_rejected(self):
        """
        When the LLM returns null for in_network_deductible_individual,
        the agent must return a policy_profile with None (not crash).
        """
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "session_id": "test-session-null",
            "raw_policy_text": "--- Page 1 ---\nPlan Name: Acme HMO. No deductible listed.",
            "errors": [],
        }

        with patch("app.agents.policy_ingestion.get_llm", return_value=_make_llm(MISSING_DEDUCTIBLE_RESPONSE)), \
             patch("app.agents.policy_ingestion.embed_document_chunks", _make_embed_fn()), \
             patch("app.agents.policy_ingestion.insert_policy_chunks", _make_insert_fn()):
            result = await policy_ingestion_node(state)

        assert "policy_profile" in result
        profile = result["policy_profile"]
        assert profile["in_network_deductible_individual"] is None
        assert profile["in_network_oop_max_individual"] is None

    @pytest.mark.asyncio
    async def test_null_fields_generate_extraction_warnings(self):
        """
        Null critical fields (deductible, OOP max) must produce warnings
        so the UI can alert the user — never silently pass through.
        """
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "session_id": "test-session-warn",
            "raw_policy_text": "--- Page 1 ---\nAcme HMO Silver plan.",
            "errors": [],
        }

        with patch("app.agents.policy_ingestion.get_llm", return_value=_make_llm(MISSING_DEDUCTIBLE_RESPONSE)), \
             patch("app.agents.policy_ingestion.embed_document_chunks", _make_embed_fn()), \
             patch("app.agents.policy_ingestion.insert_policy_chunks", _make_insert_fn()):
            result = await policy_ingestion_node(state)

        warnings = result.get("extraction_warnings", [])
        assert any("deductible" in w.lower() for w in warnings), \
            f"Expected deductible warning, got: {warnings}"
        assert any("oop max" in w.lower() or "out-of-pocket" in w.lower() for w in warnings), \
            f"Expected OOP max warning, got: {warnings}"

    @pytest.mark.asyncio
    async def test_confidence_is_medium_or_low_for_null_fields(self):
        """
        When critical fields are null, extraction_confidence must be MEDIUM or LOW.
        It must NEVER be HIGH when we have missing essential fields.
        """
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "session_id": "test-session-conf",
            "raw_policy_text": "--- Page 1 ---\nAcme HMO.",
            "errors": [],
        }

        with patch("app.agents.policy_ingestion.get_llm", return_value=_make_llm(MISSING_DEDUCTIBLE_RESPONSE)), \
             patch("app.agents.policy_ingestion.embed_document_chunks", _make_embed_fn()), \
             patch("app.agents.policy_ingestion.insert_policy_chunks", _make_insert_fn()):
            result = await policy_ingestion_node(state)

        confidence = result.get("extraction_confidence")
        assert confidence in ("MEDIUM", "LOW"), \
            f"Expected MEDIUM or LOW confidence with null fields, got: {confidence}"


class TestPolicyIngestionValidData:
    """When the LLM returns a complete, valid response, the agent should parse it cleanly."""

    @pytest.mark.asyncio
    async def test_full_valid_response_produces_policy_profile(self):
        """A complete LLM response must be parsed into a full PolicyProfile."""
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "session_id": "test-session-valid",
            "raw_policy_text": "--- Page 1 ---\nBlueCross PPO Gold. Deductible $1,500. OOP max $6,000.",
            "errors": [],
        }

        with patch("app.agents.policy_ingestion.get_llm", return_value=_make_llm(FULL_VALID_RESPONSE)), \
             patch("app.agents.policy_ingestion.embed_document_chunks", _make_embed_fn()), \
             patch("app.agents.policy_ingestion.insert_policy_chunks", _make_insert_fn()):
            result = await policy_ingestion_node(state)

        assert result.get("errors", []) == [] or result.get("policy_profile") is not None
        profile = result.get("policy_profile", {})
        assert profile.get("plan_name") == "BlueCross PPO Gold"
        assert profile.get("in_network_deductible_individual") == 1500.0
        assert profile.get("in_network_oop_max_individual") == 6000.0

    @pytest.mark.asyncio
    async def test_high_confidence_for_complete_response(self):
        """A fully populated extraction with no warnings → HIGH confidence."""
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "session_id": "test-session-high-conf",
            "raw_policy_text": "--- Page 1 ---\nBlueCross PPO Gold plan details.",
            "errors": [],
        }

        with patch("app.agents.policy_ingestion.get_llm", return_value=_make_llm(FULL_VALID_RESPONSE)), \
             patch("app.agents.policy_ingestion.embed_document_chunks", _make_embed_fn()), \
             patch("app.agents.policy_ingestion.insert_policy_chunks", _make_insert_fn()):
            result = await policy_ingestion_node(state)

        assert result.get("extraction_confidence") == "HIGH"


class TestPolicyIngestionSanityChecks:
    """Out-of-range values that ARE present (not null) should trigger range warnings."""

    @pytest.mark.asyncio
    async def test_out_of_range_deductible_generates_warning(self):
        """
        A deductible of $99,999 is outside the $0–$20,000 typical range
        and must generate a verification warning.
        """
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "session_id": "test-session-range",
            "raw_policy_text": "--- Page 1 ---\nExpensive Plan. Deductible $99,999.",
            "errors": [],
        }

        with patch("app.agents.policy_ingestion.get_llm", return_value=_make_llm(OUT_OF_RANGE_DEDUCTIBLE_RESPONSE)), \
             patch("app.agents.policy_ingestion.embed_document_chunks", _make_embed_fn()), \
             patch("app.agents.policy_ingestion.insert_policy_chunks", _make_insert_fn()):
            result = await policy_ingestion_node(state)

        warnings = result.get("extraction_warnings", [])
        assert any("deductible" in w.lower() for w in warnings), \
            f"Expected out-of-range deductible warning, got: {warnings}"

    @pytest.mark.asyncio
    async def test_out_of_range_deductible_confidence_is_not_high(self):
        """Sanity check failures must lower confidence from HIGH."""
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "session_id": "test-session-range-conf",
            "raw_policy_text": "--- Page 1 ---\nExpensive Plan.",
            "errors": [],
        }

        with patch("app.agents.policy_ingestion.get_llm", return_value=_make_llm(OUT_OF_RANGE_DEDUCTIBLE_RESPONSE)), \
             patch("app.agents.policy_ingestion.embed_document_chunks", _make_embed_fn()), \
             patch("app.agents.policy_ingestion.insert_policy_chunks", _make_insert_fn()):
            result = await policy_ingestion_node(state)

        assert result.get("extraction_confidence") != "HIGH"


class TestPolicyIngestionErrorHandling:
    """The agent must handle malformed LLM output gracefully."""

    @pytest.mark.asyncio
    async def test_invalid_json_from_llm_adds_error(self):
        """
        If the LLM returns garbled text instead of JSON, the agent must
        add an error message and NOT crash with an unhandled exception.
        """
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "session_id": "test-session-badjson",
            "raw_policy_text": "--- Page 1 ---\nSome policy text.",
            "errors": [],
        }
        garbled = "I'm sorry, I cannot extract this document. Please try again."

        with patch("app.agents.policy_ingestion.get_llm", return_value=_make_llm(garbled)), \
             patch("app.agents.policy_ingestion.embed_document_chunks", _make_embed_fn()), \
             patch("app.agents.policy_ingestion.insert_policy_chunks", _make_insert_fn()):
            result = await policy_ingestion_node(state)

        errors = result.get("errors", [])
        assert len(errors) > 0, "Expected an error message for invalid JSON output"

    @pytest.mark.asyncio
    async def test_empty_policy_text_returns_error(self):
        """Providing empty raw_policy_text must fail gracefully with an error."""
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "session_id": "test-session-empty",
            "raw_policy_text": "",
            "errors": [],
        }

        result = await policy_ingestion_node(state)

        errors = result.get("errors", [])
        assert len(errors) > 0, "Expected an error for empty policy text"

    @pytest.mark.asyncio
    async def test_session_id_derived_when_missing(self):
        """
        If session_id is not in state, the agent must derive one from the text hash
        and still complete the extraction without crashing.
        """
        from app.agents.policy_ingestion import policy_ingestion_node

        state = {
            "raw_policy_text": "--- Page 1 ---\nBlueCross PPO Gold plan.",
            "errors": [],
            # session_id intentionally omitted
        }

        with patch("app.agents.policy_ingestion.get_llm", return_value=_make_llm(FULL_VALID_RESPONSE)), \
             patch("app.agents.policy_ingestion.embed_document_chunks", _make_embed_fn()), \
             patch("app.agents.policy_ingestion.insert_policy_chunks", _make_insert_fn()):
            result = await policy_ingestion_node(state)

        # Agent must have derived a session_id and returned it
        assert result.get("session_id") is not None
        assert len(result.get("session_id", "")) > 0
