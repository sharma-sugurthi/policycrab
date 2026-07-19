import pytest
from types import SimpleNamespace

from app.services.llm_router import TaskType, get_llm_with_retry


class FakeLLM:
    def __init__(self, provider, model, should_fail=False):
        self.provider = provider
        self.model = model
        self.should_fail = should_fail
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages):
        if self.should_fail:
            raise RuntimeError(f"quota exceeded for {self.provider}/{self.model}")
        return SimpleNamespace(content="fallback worked")


@pytest.mark.asyncio
async def test_get_llm_with_retry_falls_back_to_next_provider(monkeypatch):
    candidates = [
        ("gemini", "gemini-2.5-flash", True),
        ("groq", "llama-3.3-70b-versatile", False),
    ]

    def fake_create_llm(provider, model, temperature=0.0):
        for p, m, should_fail in candidates:
            if provider == p and model == m:
                return FakeLLM(provider, model, should_fail=should_fail)
        return None

    monkeypatch.setattr("app.services.llm_router._create_llm", fake_create_llm)

    llm = get_llm_with_retry(TaskType.EXTRACTION)
    response = await llm.ainvoke([{"role": "user", "content": "hi"}])

    assert response.content == "fallback worked"
