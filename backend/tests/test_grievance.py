"""
Tests for the Grievance Agent (grievance.py).

All LLM calls and embedding API calls are mocked — these tests run
entirely offline and do NOT require API keys or a Supabase connection.

Covers:
- Routing based on Triage Agent decision (PROVIDER_CODING_ERROR vs PAYER_ILLEGAL_DENIAL)
- Mocking the RAG retrieval from the knowledge base for legal appeals
- Verifying the correct letter format and type are set in AppealOutput
- Handling missing claim/policy data gracefully
- Fallback parsing of non-JSON responses from the LLM
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── Shared Mock Factories ─────────────────────────────────────────

def _make_llm(content: str):
    """Return a mock LLM whose ainvoke() returns the given string as content."""
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_response
    return mock_llm


def _make_search_kb_fn(results=None):
    """Return a mock search_knowledge_base function that skips the real Supabase call."""
    if results is None:
        results = [
            {"concept_id": "test_reg_1", "title": "Mock ERISA Law", "full_content": "ERISA protects plan participants."},
            {"concept_id": "test_reg_2", "title": "Mock ACA Law", "full_content": "ACA mandates EHB coverage."}
        ]
    return AsyncMock(return_value=results)


def _make_generate_embedding_fn():
    """Return a mock generate_embedding function."""
    return AsyncMock(return_value=[0.1] * 768)


# ── Response Fixtures ─────────────────────────────────────────────

PROVIDER_CORRECTION_JSON = json.dumps({
    "appeal_letter": "Dear Billing Department, Please correct the claim...",
    "cited_regulations": [],
    "recommended_next_steps": [
        "Send certified mail.",
        "Wait 30 days."
    ]
})

PAYER_APPEAL_JSON = json.dumps({
    "appeal_letter": "Dear Appeals Department, This denial violates ERISA...",
    "cited_regulations": [
        {
            "statute": "ERISA 503",
            "description": "Full and fair review",
            "relevance": "Medical necessity denial requires specific guidelines."
        }
    ],
    "recommended_next_steps": [
        "File immediately.",
        "Lodge DOI complaint if denied again."
    ]
})


# ── State Fixtures ────────────────────────────────────────────────

@pytest.fixture
def minimal_state_for_grievance():
    """Provides a basic state dict with policy and claim to satisfy Grievance Agent requirements."""
    return {
        "session_id": "test-session",
        "errors": [],
        "policy_profile": {
            "plan_name": "Test PPO",
            "carrier_name": "Test Insurer",
            "plan_type": "PPO",
            "legal_classification": "FULLY_INSURED",
            "state": "CA",
            "in_network_deductible_individual": 1000.0,
            "in_network_oop_max_individual": 5000.0,
            "in_network_coinsurance": 0.20,
            "copay_schedule": {},
            "is_hsa_eligible": False,
            "requires_pcp_referral": False,
        },
        "claim_case": {
            "cpt_code": "99285",
            "cpt_description": "ER Visit",
            "icd_10_code": "I21.0",
            "icd_10_description": "Heart attack",
            "date_of_service": "2025-06-01",
            "billed_amount": 5000.0,
            "network_status": "OUT_OF_NETWORK",
            "is_emergency": True,
            "denial_reason": "MEDICAL_NECESSITY",
            "denial_carc_code": "CO-50",
        },
        "cost_breakdown": None,
        "triage_decision": None,
        "contradiction_analysis": None
    }


# ── Test Suite ────────────────────────────────────────────────────

class TestGrievanceAgentRouting:
    """The Grievance Agent must correctly route based on the Triage Agent's decision."""

    @pytest.mark.asyncio
    async def test_routes_to_provider_correction(self, minimal_state_for_grievance):
        """If Triage says PROVIDER_CODING_ERROR, draft a billing correction letter."""
        from app.agents.grievance import grievance_node
        
        state = minimal_state_for_grievance.copy()
        state["triage_decision"] = {
            "path": "PROVIDER_CODING_ERROR",
            "confidence": "HIGH",
            "coding_errors_detected": ["Missing Modifier 25"],
            "corrected_claim_instructions": "Add modifier 25 and resubmit",
            "estimated_success_probability": 0.90
        }

        # For provider correction, no RAG is used, only the LLM
        with patch("app.agents.grievance.get_llm", return_value=_make_llm(PROVIDER_CORRECTION_JSON)):
            result = await grievance_node(state)

        assert "errors" in result
        assert result.get("errors") == []
        
        appeal_data = result.get("appeal_output", {})
        assert appeal_data.get("letter_type") == "provider_correction"
        assert appeal_data.get("letter_format") == "correction_request"
        assert "Dear Billing Department" in appeal_data.get("appeal_letter", "")
        # Citations must be empty for billing corrections
        assert appeal_data.get("cited_regulations") == []

    @pytest.mark.asyncio
    async def test_routes_to_payer_appeal_by_default(self, minimal_state_for_grievance):
        """If Triage says PAYER_ILLEGAL_DENIAL (or is missing), draft a formal legal appeal."""
        from app.agents.grievance import grievance_node
        
        state = minimal_state_for_grievance.copy()
        state["triage_decision"] = {
            "path": "PAYER_ILLEGAL_DENIAL",
            "confidence": "MEDIUM",
            "estimated_success_probability": 0.70
        }

        with patch("app.agents.grievance.get_llm", return_value=_make_llm(PAYER_APPEAL_JSON)), \
             patch("app.agents.grievance.generate_embedding", new=_make_generate_embedding_fn()), \
             patch("app.agents.grievance.search_knowledge_base", new=_make_search_kb_fn()):
            result = await grievance_node(state)

        assert result.get("errors") == []
        
        appeal_data = result.get("appeal_output", {})
        assert appeal_data.get("letter_type") == "payer_appeal"
        assert appeal_data.get("letter_format") == "formal"
        assert "Dear Appeals Department" in appeal_data.get("appeal_letter", "")
        assert len(appeal_data.get("cited_regulations", [])) == 1
        assert appeal_data["cited_regulations"][0]["statute"] == "ERISA 503"

    @pytest.mark.asyncio
    async def test_mhpaea_rag_query_injected(self, minimal_state_for_grievance):
        """If denial reason is MENTAL_HEALTH_PARITY, an extra RAG query for NQTL should be injected."""
        from app.agents.grievance import grievance_node
        from app.models.enums import DenialReason
        
        state = minimal_state_for_grievance.copy()
        state["claim_case"]["denial_reason"] = DenialReason.MENTAL_HEALTH_PARITY.value
        state["triage_decision"] = {"path": "PAYER_ILLEGAL_DENIAL"}

        mock_embedding = _make_generate_embedding_fn()
        with patch("app.agents.grievance.get_llm", return_value=_make_llm(PAYER_APPEAL_JSON)), \
             patch("app.agents.grievance.generate_embedding", new=mock_embedding), \
             patch("app.agents.grievance.search_knowledge_base", new=_make_search_kb_fn()):
            await grievance_node(state)

        # Standard queries = 3. MHPAEA adds 1 extra query = 4 total calls to generate_embedding
        assert mock_embedding.call_count == 4

    @pytest.mark.asyncio
    async def test_formulary_rag_query_injected(self, minimal_state_for_grievance):
        """If denial reason is FORMULARY_EXCLUSION, an extra RAG query should be injected."""
        from app.agents.grievance import grievance_node
        from app.models.enums import DenialReason
        
        state = minimal_state_for_grievance.copy()
        state["claim_case"]["denial_reason"] = DenialReason.FORMULARY_EXCLUSION.value
        state["triage_decision"] = {"path": "PAYER_ILLEGAL_DENIAL"}

        mock_embedding = _make_generate_embedding_fn()
        with patch("app.agents.grievance.get_llm", return_value=_make_llm(PAYER_APPEAL_JSON)), \
             patch("app.agents.grievance.generate_embedding", new=mock_embedding), \
             patch("app.agents.grievance.search_knowledge_base", new=_make_search_kb_fn()):
            await grievance_node(state)

        assert mock_embedding.call_count == 4

    @pytest.mark.asyncio
    async def test_step_therapy_rag_query_injected(self, minimal_state_for_grievance):
        """If denial reason is STEP_THERAPY_REQUIRED, an extra RAG query should be injected."""
        from app.agents.grievance import grievance_node
        from app.models.enums import DenialReason
        
        state = minimal_state_for_grievance.copy()
        state["claim_case"]["denial_reason"] = DenialReason.STEP_THERAPY_REQUIRED.value
        state["triage_decision"] = {"path": "PAYER_ILLEGAL_DENIAL"}

        mock_embedding = _make_generate_embedding_fn()
        with patch("app.agents.grievance.get_llm", return_value=_make_llm(PAYER_APPEAL_JSON)), \
             patch("app.agents.grievance.generate_embedding", new=mock_embedding), \
             patch("app.agents.grievance.search_knowledge_base", new=_make_search_kb_fn()):
            await grievance_node(state)

        assert mock_embedding.call_count == 4


class TestGrievanceAgentMissingData:
    """The agent must fail gracefully if prerequisites are missing."""

    @pytest.mark.asyncio
    async def test_missing_policy_profile_returns_error(self, minimal_state_for_grievance):
        """Cannot draft a payer appeal without knowing the plan's legal classification."""
        from app.agents.grievance import grievance_node
        
        state = minimal_state_for_grievance.copy()
        state["policy_profile"] = None
        state["triage_decision"] = {"path": "PAYER_ILLEGAL_DENIAL"}

        result = await grievance_node(state)
        
        assert "errors" in result
        assert any("No policy profile" in e for e in result["errors"])
        assert "appeal_output" not in result

    @pytest.mark.asyncio
    async def test_missing_claim_case_returns_error(self, minimal_state_for_grievance):
        """Cannot draft a letter without the claim details."""
        from app.agents.grievance import grievance_node
        
        state = minimal_state_for_grievance.copy()
        state["claim_case"] = None
        state["triage_decision"] = {"path": "PROVIDER_CODING_ERROR"}

        result = await grievance_node(state)
        
        assert "errors" in result
        assert any("No claim case" in e for e in result["errors"])
        assert "appeal_output" not in result


class TestGrievanceAgentLLMResilience:
    """The agent must handle non-JSON text responses from the LLM."""

    @pytest.mark.asyncio
    async def test_fallback_parsing_for_raw_text_appeal(self, minimal_state_for_grievance):
        """If the LLM just returns the raw letter text (no JSON), capture it as the appeal_letter."""
        from app.agents.grievance import grievance_node
        
        state = minimal_state_for_grievance.copy()
        state["triage_decision"] = {"path": "PAYER_ILLEGAL_DENIAL"}
        
        raw_text_letter = "Dear Insurer, I am writing to appeal..."

        with patch("app.agents.grievance.get_llm", return_value=_make_llm(raw_text_letter)), \
             patch("app.agents.grievance.generate_embedding", new=_make_generate_embedding_fn()), \
             patch("app.agents.grievance.search_knowledge_base", new=_make_search_kb_fn()):
            result = await grievance_node(state)

        assert result.get("errors") == []
        appeal_data = result.get("appeal_output", {})
        
        # The agent should fall back and assign the raw text directly to the letter field
        assert appeal_data.get("appeal_letter") == raw_text_letter
        assert appeal_data.get("cited_regulations") == []
