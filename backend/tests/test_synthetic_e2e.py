from app.agents.graph import get_claim_evaluation_graph
from app.services.studio_engine import compile_dossier

async def test_synthetic_end_to_end():
    # 1. Synthetic Policy Profile
    policy_profile = {
        "plan_name": "Synthetic ACA Silver",
        "carrier_name": "Synthetic Health",
        "plan_type": "PPO",
        "state": "CA",
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
    assert "draft_letter" in appeal

    print("\n[E2E TEST] Pipeline generated appeal letter successfully.")
    
    # 4. Generate Dossier
    print("\n[E2E TEST] Compiling Evidence Dossier...")
    evidence = {
        "claim_id": "SYNTH-12345",
        "patient_name": "John Doe",
        "carrier_name": policy_profile["carrier_name"],
        "date_of_service": "2026-01-01",
        "billed_amount": "$3000",
        "letter_text": appeal["draft_letter"]
    }
    
    dossier = compile_dossier(evidence)
    
    assert dossier is not None
    assert dossier.cover is not None
    assert dossier.cover.claim_id == "SYNTH-12345"
    assert len(dossier.sections) > 0
    
    print("\n[E2E TEST] Synthetic E2E Test Passed Successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_synthetic_end_to_end())
