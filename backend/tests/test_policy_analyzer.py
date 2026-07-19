import pytest
from app.agents.policy_analyzer import policy_analyzer_node
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage

@pytest.mark.asyncio
async def test_policy_analyzer_no_contradiction():
    # Mocking the LLM and RAG retrieval to avoid API calls during test
    state = {
        "claim_case": {
            "cpt_code": "99213",
            "denial_reason": "Not covered",
            "is_denied": True
        },
        "policy_profile": {
            "session_id": "test_session_123"
        }
    }

    # Use unittest.mock to patch the LLM response
    with patch("app.agents.policy_analyzer.get_llm") as mock_get_llm, \
         patch("app.agents.policy_analyzer.search_knowledge_base") as mock_search, \
         patch("app.agents.policy_analyzer.generate_embedding") as mock_embed:
        
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = []
        
        mock_llm = MagicMock()
        mock_llm.ainvoke.return_value = AIMessage(content='''{"is_contradiction": false, "contradiction_strength": "NONE", "contradictions": [], "key_findings": ["No contradiction found"], "honest_assessment": "The claim is not covered.", "appeal_recommendation": "UNLIKELY_TO_WIN"}''')
        mock_get_llm.return_value = mock_llm
        
        result = await policy_analyzer_node(state)
        
        assert result["current_phase"] == "policy_analyzer"
        analysis = result["contradiction_analysis"]
        assert analysis["is_contradiction"] is False
        assert analysis["contradiction_strength"] == "NONE"
        assert analysis["appeal_recommendation"] == "UNLIKELY_TO_WIN"
