import asyncio
import json
from unittest.mock import patch
from app.agents.policy_ingestion import policy_ingestion_node
from app.agents.state import AgentState

class MockLLM:
    async def ainvoke(self, messages):
        class MockResponse:
            content = """```json
            {
              "plan_name": "Test Missing Data Plan",
              "carrier_name": "Acme Health",
              "plan_type": "HMO",
              "legal_classification": "FULLY_INSURED",
              "state": "NY",
              "in_network_deductible_individual": null,
              "in_network_oop_max_individual": null,
              "in_network_coinsurance": 0.20,
              "is_hsa_eligible": false,
              "requires_pcp_referral": true
            }
            ```"""
        return MockResponse()

async def mock_embed(*args, **kwargs):
    return [{"chunk_text": "fake", "embedding": [0.1]*768, "page_number": 1, "chunk_index": 0}]

@patch('app.agents.policy_ingestion.get_llm', return_value=MockLLM())
@patch('app.agents.policy_ingestion.embed_document_chunks', new=mock_embed)
async def main(mock_get_llm):
    fake_sbc_text = """
    Summary of Benefits and Coverage
    Plan Name: Test Missing Data Plan
    """
    
    state: AgentState = {
        "session_id": "test_session_phase1",
        "raw_policy_text": fake_sbc_text,
        "errors": []
    }
    
    result = await policy_ingestion_node(state)
    
    print("\n=== EXTRACTED POLICY PROFILE ===")
    print(json.dumps(result.get("policy_profile", {}), indent=2))
    
    print("\n=== EXTRACTION WARNINGS ===")
    for warning in result.get("extraction_warnings", []):
        print(f"⚠️ {warning}")

if __name__ == "__main__":
    asyncio.run(main())
