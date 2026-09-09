"""Table-driven tests for the deterministic success scorer. No LLM, no Supabase."""

import pytest

from app.engine.success_scorer import (
    SuccessFeatures,
    compute_success_score,
    build_success_features,
    attach_success_score,
    SCORE_FLOOR,
    SCORE_CEILING,
)


def _f(**kw) -> SuccessFeatures:
    return SuccessFeatures(**kw)


def test_nsa_violation_with_strong_contradiction_is_high():
    r = compute_success_score(_f(contradiction_strength="STRONG", nsa_violation_detected=True,
                                 triage_confidence="HIGH", policy_indexed=True, days_remaining=90))
    assert r.band == "HIGH"
    assert r.score == SCORE_CEILING          # 0.35+0.30+0.35+0.05 = 1.05 -> clamped
    assert any(f["factor"] == "nsa_violation" for f in r.factors)


def test_correctly_denied_is_capped():
    r = compute_success_score(_f(appeal_recommendation="CLAIM_CORRECTLY_DENIED", contradiction_strength="STRONG",
                                 policy_indexed=True, days_remaining=90))
    assert r.score == 0.10
    assert r.hard_rule == "CAP_CLAIM_CORRECTLY_DENIED"
    assert r.band == "VERY_LOW"


def test_unlikely_to_win_and_exception_request_caps():
    assert compute_success_score(_f(appeal_recommendation="UNLIKELY_TO_WIN", contradiction_strength="STRONG",
                                    policy_indexed=True, days_remaining=90)).score == 0.20
    r = compute_success_score(_f(appeal_recommendation="EXCEPTION_REQUEST", contradiction_strength="STRONG",
                                 nsa_violation_detected=True, policy_indexed=True, days_remaining=90))
    assert r.score == 0.60


def test_expired_deadline_floors_score():
    r = compute_success_score(_f(contradiction_strength="STRONG", nsa_violation_detected=True,
                                 policy_indexed=True, days_remaining=0))
    assert r.score == SCORE_FLOOR
    assert r.hard_rule == "DEADLINE_EXPIRED"


def test_contradiction_strength_is_monotonic():
    base = dict(policy_indexed=True, days_remaining=90)
    strong = compute_success_score(_f(contradiction_strength="STRONG", **base)).score
    moderate = compute_success_score(_f(contradiction_strength="MODERATE", **base)).score
    weak = compute_success_score(_f(contradiction_strength="WEAK", **base)).score
    none = compute_success_score(_f(contradiction_strength="NONE", **base)).score
    assert strong > moderate > weak > none


def test_provider_correction_uses_own_table():
    r = compute_success_score(_f(triage_path="PROVIDER_CODING_ERROR", triage_confidence="HIGH",
                                 denial_carc_code="CO-97", days_remaining=30))
    assert r.factors[0]["factor"] == "base_provider_correction"
    assert r.score == 0.80
    assert r.band == "HIGH"


def test_factors_sum_to_score_before_clamp():
    r = compute_success_score(_f(contradiction_strength="MODERATE", triage_confidence="LOW",
                                 policy_indexed=False, grounding_score=0.3, quality_gate_status="WARN",
                                 days_remaining=60))
    total = round(sum(f["delta"] for f in r.factors), 3)
    assert total == r.score == pytest.approx(0.35 + 0.15 - 0.05 - 0.10 - 0.10 - 0.05)
    assert r.band == "LOW"


def test_penalties_apply():
    baseline = compute_success_score(_f(policy_indexed=True, days_remaining=90)).score
    unindexed = compute_success_score(_f(policy_indexed=False, days_remaining=90)).score
    weak_ground = compute_success_score(_f(policy_indexed=True, grounding_score=0.2, days_remaining=90)).score
    assert unindexed == pytest.approx(baseline - 0.10)
    assert weak_ground == pytest.approx(baseline - 0.10)


def test_build_features_from_pipeline_dicts():
    features = build_success_features(
        appeal_output={"appeal_recommendation": "STRONG_APPEAL", "contradiction_strength": "STRONG",
                       "triage_path": "PAYER_ILLEGAL_DENIAL", "triage_confidence": "HIGH", "days_remaining": "45",
                       "appeal_framework": "STATE_EXTERNAL_REVIEW",
                       "citation_verification": {"grounding_score": 0.9}},
        claim_case={"denial_carc_code": "co-50", "is_emergency": False, "denial_reason": "MEDICAL_NECESSITY"},
        cost_breakdown={"nsa_violation_detected": False},
        triage_decision={"triage_method": "deterministic_carc"},
        policy_indexed=True,
        quality_gate={"status": "PASS"},
    )
    assert features.days_remaining == 45
    assert features.denial_carc_code == "CO-50"
    assert features.grounding_score == 0.9
    assert features.appeal_framework == "STATE_EXTERNAL_REVIEW"


def test_attach_success_score_is_additive_and_defensive():
    ao = {"appeal_recommendation": "APPEAL", "contradiction_strength": "NONE", "days_remaining": 100}
    out = attach_success_score(ao, policy_indexed=True)
    assert set(out) >= {"success_score", "success_score_band", "success_score_factors", "success_score_version"}
    assert "success_score" not in ao                      # original untouched
    assert out["success_score_version"] == "v1"
    # garbage in -> still returns a dict, never raises
    assert isinstance(attach_success_score({"days_remaining": "not-a-number"}), dict)
