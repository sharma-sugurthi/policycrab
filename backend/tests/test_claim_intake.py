from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.claim_intake import claim_intake_node
from app.models.enums import NetworkStatus


class _FakeLLM:
    def __init__(self, content):
        self.content = content

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return SimpleNamespace(content=self.content, tool_calls=[])


@pytest.mark.asyncio
async def test_claim_intake_parses_wrapped_json_response(monkeypatch):
    wrapped_json = (
        "{'type': 'text', 'text': '```json\\n"
        '{"cpt_code":"73721","cpt_description":"MRI Lower Extremity Joint Without Contrast",'
        '"icd_10_code":"M25.561","icd_10_description":"Pain in right knee",'
        '"date_of_service":"2026-07-01","billed_amount":3500.0,'
        '"provider_name":null,"facility_name":null,'
        '"network_status":"OUT_OF_NETWORK","is_emergency":false,'
        '"prior_auth_required":true,"prior_auth_obtained":false,'
        '"pcp_referral_obtained":false,"nsa_applies":false,'
        '"nsa_reason":null,"is_denied":true,'
        '"denial_reason":"MEDICAL_NECESSITY","denial_date":null,'
        '"denial_carc_code":"CO-50","denial_rarc_code":null}'
        "\\n```'}"
    )

    monkeypatch.setattr("app.agents.claim_intake.get_llm_with_retry", lambda *args, **kwargs: _FakeLLM(wrapped_json))
    monkeypatch.setattr("app.agents.claim_intake.lookup_cpt_code", AsyncMock())
    monkeypatch.setattr("app.agents.claim_intake.lookup_icd10_code", AsyncMock())

    result = await claim_intake_node(
        {
            "raw_claim_text": "I had an MRI on my right knee and it was denied.",
            "errors": [],
        }
    )

    claim = result["claim_case"]
    assert claim["cpt_code"] == "73721"
    assert claim["network_status"] == NetworkStatus.OUT_OF_NETWORK.value
    assert result["route_decision"] == "denied"