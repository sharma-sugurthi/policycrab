"""Unit tests for the deterministic extraction quality gate. No LLM, no Supabase."""

import pytest

from app.engine.quality_gate import evaluate_quality_gate, render_checklist_text
from app.agents.quality_gate import quality_gate_node, explain_blocked_node, route_after_quality_gate


def _complete_claim(**overrides) -> dict:
    claim = {
        "cpt_code": "27447", "cpt_description": "Knee replacement",
        "billed_amount": 45000.0, "network_status": "IN_NETWORK",
        "is_emergency": False, "is_denied": True,
        "denial_reason": "MEDICAL_NECESSITY", "denial_date": "2026-06-01", "denial_carc_code": "CO-50",
    }
    claim.update(overrides)
    return claim


POLICY = {"legal_classification": "FULLY_INSURED", "state": "CA"}


def _fields(result):
    return [i.field for i in result.missing_information_checklist]


def test_complete_claim_passes():
    r = evaluate_quality_gate(_complete_claim(), POLICY, None, True, "denied", mode="warn")
    assert r.status == "PASS"
    assert r.completeness_score == 1.0
    assert r.to_dict()["missing_information_checklist"] == []


def test_billed_amount_sentinel_is_critical():
    r = evaluate_quality_gate(_complete_claim(billed_amount=1.0), POLICY, None, True, "denied")
    assert "billed_amount" in r.critical_missing
    assert r.status == "WARN"


def test_cpt_sentinel_is_important():
    r = evaluate_quality_gate(_complete_claim(cpt_code="00000"), POLICY, None, True, "denied")
    assert "cpt_code" in _fields(r)
    assert "cpt_code" not in r.critical_missing


def test_missing_denial_date_is_critical_for_denied_claims_only():
    denied = evaluate_quality_gate(_complete_claim(denial_date=None), POLICY, None, True, "denied")
    assert "denial_date" in denied.critical_missing
    approved = evaluate_quality_gate(
        _complete_claim(denial_date=None, is_denied=False, denial_reason=None, denial_carc_code=None),
        POLICY, None, True, "approved",
    )
    assert "denial_date" not in _fields(approved)
    assert approved.status == "PASS"


def test_missing_carc_and_other_reason_are_important():
    claim = _complete_claim(denial_carc_code=None, denial_reason="OTHER")
    r = evaluate_quality_gate(claim, POLICY, None, True, "denied")
    assert {"denial_carc_code", "denial_reason"} <= set(_fields(r))
    assert r.critical_missing == []


def test_network_not_applicable_without_emergency_flagged():
    r = evaluate_quality_gate(_complete_claim(network_status="NOT_APPLICABLE"), POLICY, None, True, "denied")
    assert "network_status" in _fields(r)
    emergency = _complete_claim(network_status="NOT_APPLICABLE", is_emergency=True)
    ok = evaluate_quality_gate(emergency, POLICY, None, True, "denied")
    assert "network_status" not in _fields(ok)


def test_missing_legal_classification_is_critical_and_state_important():
    r = evaluate_quality_gate(_complete_claim(), {"state": None}, None, True, "denied")
    assert "legal_classification" in r.critical_missing
    assert "state" in _fields(r)


def test_unindexed_policy_is_nice_to_have_and_does_not_warn_alone():
    r = evaluate_quality_gate(_complete_claim(), POLICY, None, False, "denied")
    assert _fields(r) == ["policy_document"]
    assert r.status == "PASS"           # NICE_TO_HAVE alone never warns
    assert r.completeness_score == pytest.approx(0.95)


def test_eob_low_confidence_propagates():
    eob = {"confidence": {"billed_amount": "high", "denial_carc_code": "low", "network_status": "low"}}
    r = evaluate_quality_gate(_complete_claim(), POLICY, eob, True, "denied")
    assert {"denial_carc_code", "network_status"} <= set(_fields(r))
    assert r.field_confidence["denial_carc_code"] == "low"
    assert all(i.confidence == "low" for i in r.missing_information_checklist)


def test_eob_math_errors_are_critical():
    eob = {"confidence": {}, "validation_errors": ["allowed_amount (5000) > billed_amount (4000)"]}
    r = evaluate_quality_gate(_complete_claim(), POLICY, eob, True, "denied")
    assert "eob_math" in r.critical_missing
    assert "allowed_amount" in r.missing_information_checklist[0].why_it_matters


def test_mode_matrix():
    claim = _complete_claim(denial_date=None)   # one CRITICAL gap
    assert evaluate_quality_gate(claim, POLICY, None, True, "denied", mode="off").status == "PASS"
    assert evaluate_quality_gate(claim, POLICY, None, True, "denied", mode="warn").status == "WARN"
    assert evaluate_quality_gate(claim, POLICY, None, True, "denied", mode="block").status == "BLOCK"
    # block mode with only IMPORTANT gaps -> WARN, never BLOCK
    r = evaluate_quality_gate(_complete_claim(denial_carc_code=None), POLICY, None, True, "denied", mode="block")
    assert r.status == "WARN"


def test_benchmark_mode_always_passes():
    r = evaluate_quality_gate({}, {}, None, False, "denied", mode="block", benchmark_mode=True)
    assert r.status == "PASS"


def test_malformed_inputs_do_not_raise():
    r = evaluate_quality_gate("not a dict", 42, ["x"], False, "denied")
    assert r.status in ("WARN", "PASS")


def test_render_checklist_text_orders_critical_first():
    claim = _complete_claim(denial_date=None, denial_carc_code=None)
    gate = evaluate_quality_gate(claim, POLICY, None, True, "denied").to_dict()
    text = render_checklist_text(gate)
    assert text.index("Denial Date (CRITICAL)") < text.index("Denial Carc Code (IMPORTANT)")
    assert "Where to find it" in text
    assert render_checklist_text({}) == "The claim information looks complete."


# ── Node + routing ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quality_gate_node_writes_state_and_never_errors(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "quality_gate_mode", "warn")
    state = {"claim_case": _complete_claim(denial_date=None), "policy_profile": POLICY,
             "policy_indexed": True, "route_decision": "denied", "errors": []}
    result = await quality_gate_node(state)
    assert "errors" not in result
    assert result["quality_gate"]["status"] == "WARN"
    assert result["quality_gate"]["critical_missing"] == ["denial_date"]


@pytest.mark.asyncio
async def test_quality_gate_node_block_mode_routes_to_explain_blocked(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "quality_gate_mode", "block")
    state = {"claim_case": _complete_claim(denial_date=None), "policy_profile": POLICY,
             "policy_indexed": True, "route_decision": "denied", "errors": [], "explanations": {}}
    state.update(await quality_gate_node(state))
    assert route_after_quality_gate(state) == "explain_blocked"

    blocked = await explain_blocked_node(state)
    assert blocked["appeal_output"] is None
    assert blocked["current_phase"] == "quality_gate_blocked"
    assert "Denial Date (CRITICAL)" in blocked["explanations"]["quality_gate"]


def test_route_after_quality_gate_defers_to_cost_routing():
    assert route_after_quality_gate({"quality_gate": {"status": "WARN"}, "route_decision": "denied"}) == "policy_analyzer"
    assert route_after_quality_gate({"quality_gate": {"status": "PASS"}, "route_decision": "approved"}) == "explain_cost"
    assert route_after_quality_gate({"route_decision": "denied"}) == "policy_analyzer"


def test_grievance_known_data_gaps_paragraph():
    from app.agents.grievance import _format_known_data_gaps
    assert _format_known_data_gaps(None) == ""
    assert _format_known_data_gaps({"missing_information_checklist": []}) == ""
    gate = evaluate_quality_gate(_complete_claim(denial_date=None), POLICY, None, False, "denied").to_dict()
    text = _format_known_data_gaps(gate)
    assert "KNOWN DATA GAPS" in text
    assert "[DENIAL DATE]" in text
    assert "policy_document" not in text      # NICE_TO_HAVE items are not sent to the LLM
