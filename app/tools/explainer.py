"""
Explanation Tool — translates insurance jargon into plain English.

This is a cross-cutting tool available to ALL agents. It takes
technical insurance/legal output and produces a patient-friendly
explanation that is accurate, clear, and actionable.
"""

from langchain_core.tools import tool
from app.services.llm_router import get_llm, TaskType


EXPLAINER_SYSTEM_PROMPT = """You are a health insurance explainer. Your job is to translate 
complex insurance jargon, legal language, and medical billing terms into plain, 
clear English that a patient with no insurance knowledge can understand.

Rules:
1. NEVER change the meaning or omit critical facts. Accuracy is non-negotiable.
2. Use short sentences. Avoid passive voice.
3. When mentioning dollar amounts, always show the math simply.
4. When mentioning deadlines, always state the exact date AND the number of days remaining.
5. When mentioning legal rights, frame them as actionable steps the patient can take.
6. Use analogies only when they genuinely help (e.g., "A deductible is like a yearly 
   threshold — you pay this amount first before your insurance starts sharing the cost").
7. NEVER say "I" or "we". Speak directly to the patient using "you" and "your".
8. End with 1-3 specific next steps the patient should take.
9. Do NOT add any information not present in the input. Do NOT hallucinate facts.
"""


@tool
async def explain_in_plain_english(
    technical_text: str,
    context: str = "",
) -> str:
    """Convert complex insurance/legal language into patient-friendly plain English.

    Use this tool whenever you have technical output that needs to be
    explained to the patient. This includes:
    - Policy terms and conditions
    - Cost breakdowns (deductible, coinsurance, OOP max)
    - Denial reasons and CARC/RARC codes
    - Appeal rights and deadlines
    - Legal frameworks (ERISA, NSA, ACA)

    Args:
        technical_text: The technical content to explain in plain English.
        context: Optional additional context about the patient's situation.
    """
    llm = get_llm(TaskType.EXPLANATION, temperature=0.3)

    prompt = f"""Explain the following insurance information in plain English for a patient:

{technical_text}

{"Additional context: " + context if context else ""}

Provide a clear, accurate explanation followed by specific next steps."""

    from langchain_core.messages import SystemMessage, HumanMessage
    messages = [
        SystemMessage(content=EXPLAINER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    return response.content
