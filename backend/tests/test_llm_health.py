import asyncio
from app.services.llm_router import _create_llm

import pytest

@pytest.mark.asyncio
async def test_all_models():
    providers = [
        ("gemini",      "gemini-2.5-flash",              "PRIMARY — Extraction/Chat/Tools"),
        ("gemini",      "gemini-2.5-pro",                "PRIMARY — Reasoning/Legal Writing"),
        ("groq",        "llama-3.3-70b-versatile",       "FALLBACK 1 — Explanation/Speed"),
        ("cerebras",    "gemma-4-31b",                   "FALLBACK 2 — Cerebras (Ultra-fast)"),
        ("openrouter",  "google/gemma-4-31b-it:free",    "FALLBACK 3 — OpenRouter Gemma"),
    ]

    print("=" * 65)
    print("  PolicyCrab — Final LLM Provider Health Check")
    print("=" * 65)
    passed, failed = 0, 0
    for provider, model, role in providers:
        llm = _create_llm(provider, model)
        if not llm:
            print(f"⚫ SKIP    {role}\n          No API key found")
            continue
        try:
            print(f"⏳ {role}...")
            response = await llm.ainvoke("Reply with just the word OK.")
            content = response.content[:20].strip()
            print(f"✅ PASS    {role} → '{content}'")
            passed += 1
        except Exception as e:
            print(f"❌ FAIL    {role}\n          {str(e)[:100]}")
            failed += 1

    print("=" * 65)
    print(f"  Final Score: {passed} passed / {passed + failed} total")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(test_all_models())
