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
        {"provider": "gemini", "model": "gemini-2.5-flash"},
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    ]
    
    # Override the registry just for this test so we know it has fallbacks
    monkeypatch.setitem(
        __import__("app.services.llm_router", fromlist=["_MODEL_REGISTRY"])._MODEL_REGISTRY,
        TaskType.EXTRACTION,
        candidates
    )

    def fake_create_llm(provider, model, temperature=0.0):
        if provider == "gemini":
            return FakeLLM(provider, model, should_fail=True)
        if provider == "groq":
            return FakeLLM(provider, model, should_fail=False)
        return None

    monkeypatch.setattr("app.services.llm_router._create_llm", fake_create_llm)

    llm = get_llm_with_retry(TaskType.EXTRACTION)
    response = await llm.ainvoke([{"role": "user", "content": "hi"}])

    assert response.content == "fallback worked"
