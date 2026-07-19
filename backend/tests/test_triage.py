import pytest
from app.agents.triage import triage_node
from app.models.enums import NetworkStatus

@pytest.mark.asyncio
async def test_triage_deterministic_nsa():
    state = {
        "claim_case": {
            "cpt_code": "00100",
            "cpt_description": "Anesthesia",
            "icd_10_code": "R07.9",
            "date_of_service": "2024-01-01",
            "billed_amount": 1000,
            "network_status": NetworkStatus.OUT_OF_NETWORK,
            "facility_network_status": NetworkStatus.IN_NETWORK,
            "ancillary_service_type": "anesthesia",
            "is_emergency": False,
            "is_denied": True
        },
        "cost_breakdown": {
            "billed_amount": 1000,
            "allowed_amount": 100,
            "total_patient_responsibility": 100,
            "total_insurer_payout": 0,
            "illegal_balance_billed_amount": 900,
            "claim_status": "DENIED",
            "calculation_notes": []
        },
        "policy_profile": None,
        "contradiction_analysis": None
    }
    
    result = await triage_node(state)
    assert result["current_phase"] == "triage"
    decision = result["triage_decision"]
    assert decision["path"] == "PAYER_ILLEGAL_DENIAL"
    assert decision["confidence"] == "HIGH"
    assert "NSA Scenario B" in decision["primary_reason"]
    assert decision["triage_method"] == "deterministic_nsa"

@pytest.mark.asyncio
async def test_triage_deterministic_provider_error():
    state = {
        "claim_case": {
            "cpt_code": "99213",
            "date_of_service": "2024-01-01",
            "billed_amount": 150,
            "network_status": NetworkStatus.IN_NETWORK,
            "facility_network_status": NetworkStatus.IN_NETWORK,
            "ancillary_service_type": None,
            "is_emergency": False,
            "is_denied": True,
            "denial_carc_code": "CO-97"
        },
        "cost_breakdown": None,
        "policy_profile": None,
        "contradiction_analysis": None
    }
    
    result = await triage_node(state)
    decision = result["triage_decision"]
    assert decision["path"] == "PROVIDER_CODING_ERROR"
    assert decision["confidence"] == "HIGH"
    assert decision["triage_method"] == "deterministic_carc"
    assert "CO-97" in decision["primary_reason"]
