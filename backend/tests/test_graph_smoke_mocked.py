"""
End-to-end smoke test of the compiled claim-evaluation graph with EVERY
LLM / embedding / Supabase call mocked.

This is the single test that proves the graph wiring (including the new
quality_gate and appeal_qa nodes) does not break the existing pipeline:
  - denied claim: intake → cost → policy_analyzer → triage → grievance → appeal_qa → explain_appeal
  - approved claim: intake → cost → explain_cost
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


FRONTEND_READ_KEYS = [
    "appeal_recommendation", "contradiction_strength", "policy_citations",
    "contradiction_detected", "appeal_deadline", "days_remaining", "appeal_letter",
    "triage_path", "triage_confidence", "recommended_next_steps", "honest_assessment",
    "cited_regulations", "appeal_framework", "triage_action_summary",
]


def _llm(content: str):
    resp = MagicMock()
    resp.content = content
    llm = AsyncMock()
    llm.ainvoke.return_value = resp
    return llm


DENIED_CLAIM_JSON = json.dumps({
    "cpt_code": "27447",
    "cpt_description": "Total Knee Replacement",
    "icd_10_code": "M17.11",
    "icd_10_description": "Primary osteoarthritis, right knee",
    "date_of_service": "2026-05-10",
    "billed_amount": 45000.0,
    "provider_name": "Dr. Smith",
    "facility_name": "General Hospital",
    "network_status": "IN_NETWORK",
    "is_emergency": False,
    "prior_auth_obtained": True,
    "prior_auth_required": True,
    "is_denied": True,
    "denial_reason": "MEDICAL_NECESSITY",
    "denial_date": "2026-06-01",
    "denial_carc_code": "CO-50",
})

APPROVED_CLAIM_JSON = json.dumps({
    "cpt_code": "99213",
    "cpt_description": "Office visit",
    "icd_10_code": "J06.9",
    "icd_10_description": "Upper respiratory infection",
    "date_of_service": "2026-05-10",
    "billed_amount": 250.0,
    "network_status": "IN_NETWORK",
    "is_emergency": False,
    "prior_auth_obtained": None,
    "prior_auth_required": False,
    "is_denied": False,
})

ANALYZER_JSON = json.dumps({
    "is_contradiction": True,
    "contradiction_strength": "STRONG",
    "appeal_recommendation": "STRONG_APPEAL",
    "appeal_strength_rationale": "Policy covers medically necessary joint replacement.",
    "contradictions": [
        {
            "page_number": 12,
            "exact_clause_text": "Joint replacement surgery is covered when medically necessary.",
            "contradiction_explanation": "The denial ignores this coverage clause.",
            "insurer_mistake": "Applied an internal guideline not in the plan document.",
        }
    ],
    "supporting_clauses": [],
    "key_findings": ["Coverage clause found on page 12."],
    "honest_assessment": "Strong case.",
})

GRIEVANCE_JSON = json.dumps({
    "appeal_letter": (
        "Dear Appeals Department, this denial violates 29 CFR § 2560.503-1. "
        "On page 12 of the policy, it states: Joint replacement surgery is covered when medically necessary."
    ),
    "cited_regulations": [
        {"statute": "29 CFR § 2560.503-1", "description": "Full and fair review", "relevance": "Medical necessity denial"},
    ],
    "recommended_next_steps": ["Send via certified mail."],
})

POLICY_CHUNKS = [
    {
        "page_number": 12,
        "chunk_index": 0,
        "chunk_text": "Section 4 - Covered Services. Joint replacement surgery is covered when medically necessary.",
        "section_heading": "BENEFITS",
        "similarity": 0.8,
    }
]

KB_CHUNKS = [
    {
        "concept_id": "erisa_claims_procedure",
        "title": "ERISA Claims Procedure",
        "full_content": "29 CFR § 2560.503-1 requires a full and fair review of denied claims.",
        "semantic_summary": "ERISA claims procedure regulation.",
        "domain": "regulatory",
        "jurisdiction": "federal",
    }
]


def _base_state(policy_profile: dict, claim_text: str) -> dict:
    return {
        "messages": [],
        "raw_policy_text": "",
        "raw_claim_text": claim_text,
        "benchmark_policy_excerpt": None,
        "policy_profile": policy_profile,
        "claim_case": None,
        "allowed_amount": None,
        "cost_breakdown": None,
        "appeal_output": None,
        "current_phase": "intake",
        "route_decision": "",
        "errors": [],
        "extraction_warnings": [],
        "extraction_confidence": None,
        "explanations": {},
        "session_id": "smoke-session",
        "policy_indexed": True,
    }


def _patches(intake_json: str):
    return [
        patch("app.agents.claim_intake.get_llm_with_retry", return_value=_llm(intake_json)),
        patch("app.agents.policy_analyzer.get_llm", return_value=_llm(ANALYZER_JSON)),
        patch("app.agents.policy_analyzer.generate_embedding", new=AsyncMock(return_value=[0.1] * 768)),
        patch("app.agents.policy_analyzer.generate_embeddings_batch",
              new=AsyncMock(side_effect=lambda qs: [[0.1] * 768 for _ in qs])),
        patch("app.agents.policy_analyzer.search_knowledge_base", new=AsyncMock(return_value=POLICY_CHUNKS)),
        patch("app.agents.policy_analyzer.fetch_structural_anchor", new=AsyncMock(return_value=[])),
        patch("app.agents.triage.get_llm", return_value=_llm(json.dumps({
            "path": "PAYER_ILLEGAL_DENIAL", "confidence": "HIGH", "primary_reason": "x",
            "coding_errors_detected": [], "legal_violations_detected": ["ERISA"],
            "action_summary": "Appeal", "estimated_success_probability": 0.7,
        }))),
        patch("app.agents.grievance.get_llm", return_value=_llm(GRIEVANCE_JSON)),
        patch("app.agents.grievance.generate_embedding", new=AsyncMock(return_value=[0.1] * 768)),
        patch("app.agents.grievance.search_knowledge_base", new=AsyncMock(return_value=KB_CHUNKS)),
        patch("app.agents.explanation.get_llm", return_value=_llm("Plain English explanation.")),
    ]


@pytest.mark.asyncio
async def test_denied_claim_runs_full_pipeline_including_appeal_qa(sample_ppo_policy):
    from app.agents.graph import get_claim_evaluation_graph

    state = _base_state(
        sample_ppo_policy.model_dump(mode="json"),
        "My knee replacement was denied as not medically necessary, CARC CO-50, denial dated 2026-06-01.",
    )

    patches = _patches(DENIED_CLAIM_JSON)
    for p in patches:
        p.start()
    try:
        result = await get_claim_evaluation_graph().ainvoke(state)
    finally:
        for p in patches:
            p.stop()

    assert result["errors"] == [], f"pipeline produced errors: {result['errors']}"
    assert result["route_decision"] == "denied"

    appeal = result["appeal_output"]
    assert appeal is not None
    for key in FRONTEND_READ_KEYS:
        assert key in appeal, f"frontend-read key '{key}' missing from appeal_output"
    assert appeal["plain_english_summary"] == "Plain English explanation."

    # quality gate ran (complete claim -> PASS) and appeal_qa ran and reported
    assert result["quality_gate"]["status"] == "PASS"
    assert isinstance(result.get("citation_verification"), dict)
    assert result["citation_verification"]["status"] in ("VERIFIED", "PARTIAL")
    # The one cited statute is in the allowlist -> verified, letter untouched
    assert appeal["cited_regulations"][0]["verification_status"] == "VERIFIED"
    assert "[VERIFY" not in appeal["appeal_letter"]
    # Policy clause quoted on page 12 matches the retrieved chunk
    assert appeal["policy_citations"][0]["verification_status"] == "VERIFIED"
    # Deterministic success score attached with a transparent factor list
    assert 0.0 <= appeal["success_score"] <= 1.0
    assert appeal["success_score_band"] in ("HIGH", "MEDIUM", "LOW", "VERY_LOW")
    assert any(f["factor"] == "contradiction_strong" for f in appeal["success_score_factors"])
    # LLM estimate is preserved untouched alongside it
    assert appeal["estimated_success_probability"] == 0.7
    # retrieval provenance surfaced for the verifier
    assert result["knowledge_chunks_retrieved"][0]["concept_id"] == "erisa_claims_procedure"
    assert result["policy_chunks_retrieved"][0]["page_number"] == 12


@pytest.mark.asyncio
async def test_approved_claim_skips_appeal_path(sample_ppo_policy):
    from app.agents.graph import get_claim_evaluation_graph

    state = _base_state(
        sample_ppo_policy.model_dump(mode="json"),
        "I had a routine in-network office visit for a cold and it was paid.",
    )

    patches = _patches(APPROVED_CLAIM_JSON)
    for p in patches:
        p.start()
    try:
        result = await get_claim_evaluation_graph().ainvoke(state)
    finally:
        for p in patches:
            p.stop()

    assert result["errors"] == []
    assert result["route_decision"] == "approved"
    assert result.get("appeal_output") is None
    assert result["quality_gate"]["status"] == "PASS"
    assert result["cost_breakdown"]["claim_status"] in ("APPROVED", "PARTIALLY_APPROVED")
    assert "calculation" in result["explanations"]
