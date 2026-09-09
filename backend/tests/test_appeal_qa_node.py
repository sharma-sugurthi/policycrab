"""
Tests for the deterministic appeal_qa node (app/agents/appeal_qa.py).

No LLM, no Supabase. The node must:
  - pass a full AppealOutput through with only ADDITIVE keys
  - never touch the keys the frontend reads
  - never raise / never add to errors
  - skip (not crash) on the benchmark-shaped appeal_output and on None
"""

import pytest

from app.agents.appeal_qa import appeal_qa_node


FRONTEND_READ_KEYS = [
    "appeal_recommendation", "contradiction_strength", "policy_citations",
    "contradiction_detected", "appeal_deadline", "days_remaining", "appeal_letter",
    "triage_path", "triage_confidence", "recommended_next_steps", "honest_assessment",
    "cited_regulations", "appeal_framework", "triage_action_summary",
    "estimated_success_probability",
]


def _full_appeal_output() -> dict:
    return {
        "appeal_framework": "ERISA_FEDERAL",
        "denial_reason": "MEDICAL_NECESSITY",
        "denial_date": "2026-06-01",
        "appeal_deadline": "2026-11-28",
        "days_remaining": 120,
        "appeal_letter": "Dear Appeals Department, under 29 CFR § 2560.503-1 you must provide a full and fair review.",
        "letter_type": "payer_appeal",
        "letter_format": "formal",
        "triage_path": "PAYER_ILLEGAL_DENIAL",
        "triage_confidence": "HIGH",
        "triage_action_summary": "File a formal appeal.",
        "estimated_success_probability": 0.7,
        "cited_regulations": [
            {"statute": "29 CFR § 2560.503-1", "description": "Full and fair review", "relevance": "Medical necessity"},
        ],
        "cited_knowledge_chunks": ["erisa_claims_procedure"],
        "policy_citations": [],
        "contradiction_detected": False,
        "contradiction_strength": "NONE",
        "appeal_recommendation": "APPEAL",
        "honest_assessment": "Reasonable chance.",
        "plain_english_summary": "",
        "recommended_next_steps": ["Send certified mail."],
    }


@pytest.mark.asyncio
async def test_full_appeal_output_passes_through_with_additive_keys_only():
    original = _full_appeal_output()
    state = {
        "appeal_output": dict(original),
        "knowledge_chunks_retrieved": [
            {
                "concept_id": "erisa_claims_procedure",
                "title": "ERISA",
                "full_content": "29 CFR § 2560.503-1 requires full and fair review.",
            }
        ],
        "policy_chunks_retrieved": [],
        "errors": [],
    }

    result = await appeal_qa_node(state)

    assert "errors" not in result, "appeal_qa must never write errors"
    out = result["appeal_output"]
    for key in FRONTEND_READ_KEYS:
        if key in ("cited_regulations", "policy_citations"):
            # Verifier may ADD keys per item (verification_status, ...) but never change or drop the originals.
            assert len(out[key]) == len(original[key])
            for new_item, old_item in zip(out[key], original[key]):
                assert old_item.items() <= new_item.items(), f"'{key}' item lost or changed original fields"
        else:
            assert out[key] == original[key], f"frontend-read key '{key}' must be unchanged"
    assert out["cited_regulations"][0]["verification_status"] == "VERIFIED"
    # The verified letter must be untouched (no [VERIFY] marker for a grounded statute)
    assert out["appeal_letter"] == original["appeal_letter"]
    # Original dict must not be mutated in place
    assert "citation_verification" not in original
    assert "verification_status" not in original["cited_regulations"][0]
    assert result["current_phase"] == "appeal"
    assert isinstance(result["citation_verification"], dict)
    assert "status" in result["citation_verification"]


@pytest.mark.asyncio
async def test_benchmark_shape_is_skipped_untouched():
    benchmark_output = {
        "appeal_letter": "[BENCHMARK MODE] bypassed",
        "legal_citations": [],
        "next_steps": ["Submit"],
        "appeal_recommendation": "STRONG_APPEAL",
    }
    state = {"appeal_output": dict(benchmark_output), "errors": []}

    result = await appeal_qa_node(state)

    assert result["citation_verification"]["status"] == "SKIPPED"
    assert "appeal_output" not in result, "benchmark stub must pass through untouched"
    assert "errors" not in result


@pytest.mark.asyncio
async def test_none_appeal_output_does_not_raise():
    result = await appeal_qa_node({"appeal_output": None, "errors": ["earlier failure"]})

    assert result["citation_verification"]["status"] == "SKIPPED"
    assert "errors" not in result


@pytest.mark.asyncio
async def test_quality_gate_is_attached_when_present():
    state = {
        "appeal_output": _full_appeal_output(),
        "quality_gate": {"status": "WARN", "missing_information_checklist": [{"field": "denial_date"}]},
        "errors": [],
    }

    result = await appeal_qa_node(state)

    assert result["appeal_output"]["quality_gate"]["status"] == "WARN"
