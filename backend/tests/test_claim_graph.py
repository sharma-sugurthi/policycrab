"""Regression tests for claim graph cost orchestration."""

import pytest

from app.agents.graph import cost_calculation_node


@pytest.mark.asyncio
async def test_cost_node_uses_billed_amount_estimate_when_allowed_amount_missing(
    sample_ppo_policy,
    sample_claim_in_network,
):
    state = {
        "messages": [],
        "raw_policy_text": "",
        "raw_claim_text": "",
        "policy_profile": sample_ppo_policy.model_dump(mode="json"),
        "claim_case": sample_claim_in_network.model_dump(mode="json"),
        "allowed_amount": None,
        "cost_breakdown": None,
        "appeal_output": None,
        "current_phase": "calculation",
        "route_decision": "",
        "errors": [],
        "explanations": {},
    }

    result = await cost_calculation_node(state)
    cost = result["cost_breakdown"]

    assert cost["allowed_amount"] == sample_claim_in_network.billed_amount
    assert cost["allowed_amount"] != sample_claim_in_network.billed_amount * 0.60
    assert cost["allowed_amount_source"] == "billed_amount_estimate"
    assert "ESTIMATE ONLY" in cost["calculation_notes"][0]


@pytest.mark.asyncio
async def test_cost_node_uses_user_supplied_eob_allowed_amount(
    sample_ppo_policy,
    sample_claim_in_network,
):
    state = {
        "messages": [],
        "raw_policy_text": "",
        "raw_claim_text": "",
        "policy_profile": sample_ppo_policy.model_dump(mode="json"),
        "claim_case": sample_claim_in_network.model_dump(mode="json"),
        "allowed_amount": 1200.0,
        "cost_breakdown": None,
        "appeal_output": None,
        "current_phase": "calculation",
        "route_decision": "",
        "errors": [],
        "explanations": {},
    }

    result = await cost_calculation_node(state)
    cost = result["cost_breakdown"]

    assert cost["allowed_amount"] == 1200.0
    assert cost["allowed_amount_source"] == "eob"
    assert "supplied by the user" in cost["calculation_notes"][0]
