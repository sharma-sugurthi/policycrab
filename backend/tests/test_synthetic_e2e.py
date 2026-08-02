import os
import pytest
from app.agents.graph import get_claim_evaluation_graph
from app.services.studio_engine import compile_dossier

@pytest.mark.asyncio
async def test_synthetic_end_to_end():
    # Only run E2E test if a real API key is available
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key or len(api_key) < 15 or api_key == "dummy":
        pytest.skip("Skipping synthetic E2E test due to missing real GEMINI_API_KEY")
    # 1. Synthetic Policy Profile
    policy_profile = {
        "plan_name": "Synthetic ACA Silver",
        "carrier_name": "Synthetic Health",
        "plan_type": "PPO",
        "state": "CA",
        "legal_classification": "INDIVIDUAL_ACA",
        "in_network_deductible_individual": 1000,
        "in_network_oop_max_individual": 5000,
        "in_network_coinsurance_percent": 20,
    }

    # 2. Run the graph with a synthetic claim text
    graph = get_claim_evaluation_graph()
    
    initial_state = {
        "messages": [],
        "raw_policy_text": "Synthetic Policy Document",
        "raw_claim_text": "I went to the ER on Jan 1 2026. The billed amount was $3000. It was denied because they said it wasn't an emergency, but I had chest pain.",
        "policy_profile": policy_profile,
        "session_id": None,
        "policy_indexed": False,
        "current_phase": "intake",
        "errors": []
    }

    print("\n[E2E TEST] Running AI Claim Pipeline...")
    final_state = await graph.ainvoke(initial_state)

    # 3. Verify Graph Output
    assert final_state["route_decision"] == "denied", "Claim should be routed as denied"
    assert "appeal_output" in final_state
    appeal = final_state["appeal_output"]
    assert appeal is not None
    assert "appeal_letter" in appeal

    print("\n[E2E TEST] Pipeline generated appeal letter successfully.")
    
    # 4. Generate Dossier
    print("\n[E2E TEST] Compiling Evidence Dossier...")
    evidence = {
        "policy_profile": policy_profile,
        "appeal_output": appeal,
        "letter_text": appeal["appeal_letter"]
    }
    
    dossier = compile_dossier(evidence)
    
    assert dossier is not None
    assert dossier.cover is not None
    assert dossier.cover.get("carrier_name") == "Synthetic Health"
    assert len(dossier.sections) > 0
    
    print("\n[E2E TEST] Synthetic E2E Test Passed Successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_synthetic_end_to_end())
