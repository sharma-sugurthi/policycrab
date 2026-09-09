"""
LLM-free regression suite over ALL benchmark case files.

Runs only the deterministic engines exactly as the pipeline wires them:
  build_claim_from_overrides → calculate_cost → route_to_appeal_framework →
  calculate_appeal_deadline → deterministic_triage → evaluate_quality_gate →
  compute_success_score

No Supabase, no model calls, so it is safe for CI and finishes in seconds. It
guards the ground truth the 200 synthetic cases encode (NSA detection, CARC
routing, correct-denial handling) and the new Accuracy Core engines against
regressions. It does NOT assert anything the LLM decides (contradiction
analysis, letter text).
"""

import json
from pathlib import Path

import pytest

from app.agents.claim_intake import build_claim_from_overrides
from app.agents.triage import deterministic_triage
from app.engine.cost_calculator import calculate_cost
from app.engine.regulatory_router import route_to_appeal_framework
from app.engine.deadline_calculator import calculate_appeal_deadline
from app.engine.quality_gate import evaluate_quality_gate
from app.engine.success_scorer import build_success_features, compute_success_score
from app.models.policy import PolicyProfile
from app.models.enums import AppealFramework

BENCH_DIR = Path(__file__).resolve().parents[1] / "benchmarks"
CASES_DIR = BENCH_DIR / "cases"
GATE_CASES_DIR = BENCH_DIR / "cases_gate"

KNOWN_RECOMMENDATIONS = {"STRONG_APPEAL", "APPEAL", "EXCEPTION_REQUEST", "UNLIKELY_TO_WIN", "CLAIM_CORRECTLY_DENIED"}


def _load_cases(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]


CASES = _load_cases(CASES_DIR)
GATE_CASES = _load_cases(GATE_CASES_DIR)


def _run_deterministic(case: dict) -> dict:
    """Mirror the pipeline's deterministic path for one benchmark case."""
    policy = PolicyProfile(**case["policy_profile"])
    claim = build_claim_from_overrides(
        case.get("claim_overrides") or {}, case.get("claim_description", ""), case.get("allowed_amount")
    )
    allowed = case.get("allowed_amount") or claim.billed_amount
    cost = calculate_cost(policy, claim, allowed_amount=min(allowed, claim.billed_amount))
    framework = route_to_appeal_framework(policy, claim)
    deadline = calculate_appeal_deadline(framework, claim.denial_date, state_code=policy.state)

    # Policy Analyzer is an LLM step — feed triage only what a benchmark expects, if given.
    expected = case.get("expected", {})
    contradiction = None
    if expected.get("appeal_recommendation") in {"CLAIM_CORRECTLY_DENIED", "UNLIKELY_TO_WIN"}:
        contradiction = {"appeal_recommendation": expected["appeal_recommendation"], "honest_assessment": "benchmark"}
    triage = deterministic_triage(claim, cost, contradiction, benchmark_mode=True)

    # Corpus cases are built from overrides (dates/amounts always present) → benchmark mode, as in the pipeline.
    gate = evaluate_quality_gate(
        claim.model_dump(mode="json"), case["policy_profile"], case.get("eob_extraction"),
        policy_indexed=True, route_decision="denied" if claim.is_denied else "approved",
        mode=case.get("quality_gate_mode", "warn"), benchmark_mode=True,
    )
    features = build_success_features(
        {"appeal_recommendation": expected.get("appeal_recommendation", "APPEAL"),
         "triage_path": (triage or {}).get("path", "PAYER_ILLEGAL_DENIAL"),
         "triage_confidence": (triage or {}).get("confidence", "LOW"),
         "days_remaining": deadline["days_remaining"], "appeal_framework": framework.value},
        claim.model_dump(mode="json"), cost.model_dump(mode="json"), triage, contradiction,
        policy_indexed=True, quality_gate=gate.to_dict(),
    )
    score = compute_success_score(features)
    return {"claim": claim, "cost": cost, "framework": framework, "deadline": deadline,
            "triage": triage, "gate": gate, "score": score}


@pytest.mark.skipif(not CASES, reason="benchmarks/cases not present")
def test_benchmark_corpus_shape():
    assert len(CASES) == 200
    for case in CASES:
        assert case["expected"]["appeal_recommendation"] in KNOWN_RECOMMENDATIONS, case["id"]
        assert case["expected"].get("route_decision") in ("denied", "approved"), case["id"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_deterministic_engines_on_every_case(case):
    out = _run_deterministic(case)
    claim, cost, framework, triage, gate, score = (
        out["claim"], out["cost"], out["framework"], out["triage"], out["gate"], out["score"]
    )

    assert isinstance(framework, AppealFramework)
    assert out["deadline"]["days_remaining"] is not None
    # Benchmark overrides always supply dates/amounts → gate passes (benchmark mode)
    assert gate.status == "PASS", (case["id"], gate.critical_missing)
    assert 0.0 < score.score <= 0.95

    category = case.get("category")
    expected = case["expected"]

    if category == "nsa_balance_billing" and expected.get("nsa_violation_detected"):
        assert cost.nsa_violation_detected, case["id"]
        assert triage is not None and triage["triage_method"] == "deterministic_nsa", case["id"]
        assert triage["path"] == "PAYER_ILLEGAL_DENIAL"
        assert score.band == "HIGH", (case["id"], score.factors)

    correctly_denied = expected["appeal_recommendation"] in {"CLAIM_CORRECTLY_DENIED", "UNLIKELY_TO_WIN"}

    # Rule precedence mirrors the pipeline: an analyzer verdict of "correctly denied"
    # wins over CARC routing. Only assert CARC routing when no such verdict applies.
    carc = (claim.denial_carc_code or "").upper()
    if carc == "CO-97" and not correctly_denied:
        assert triage is not None and triage["path"] == "PROVIDER_CODING_ERROR", case["id"]
        assert triage["triage_method"] == "deterministic_carc"

    if correctly_denied:
        assert triage is not None and triage["triage_method"] == "deterministic_correct_denial", case["id"]
        assert score.score <= 0.20, (case["id"], score.score)
        assert score.hard_rule and score.hard_rule.startswith("CAP_")


@pytest.mark.skipif(not GATE_CASES, reason="benchmarks/cases_gate not present")
@pytest.mark.parametrize("case", GATE_CASES, ids=lambda c: c["id"])
def test_quality_gate_cases(case):
    """Hand-written cases with deliberately missing data must trip the gate."""
    policy = case["policy_profile"]
    claim = case["claim_case"]
    expected = case["expected"]

    warn = evaluate_quality_gate(claim, policy, case.get("eob_extraction"), policy_indexed=True,
                                 route_decision="denied", mode="warn")
    assert warn.status == expected["warn_status"], (case["id"], warn.to_dict())
    assert set(expected.get("critical_missing", [])) <= set(warn.critical_missing), case["id"]
    for field in expected.get("checklist_fields", []):
        assert field in [i.field for i in warn.missing_information_checklist], (case["id"], field)

    block = evaluate_quality_gate(claim, policy, case.get("eob_extraction"), policy_indexed=True,
                                  route_decision="denied", mode="block")
    assert block.status == expected["block_status"], case["id"]
