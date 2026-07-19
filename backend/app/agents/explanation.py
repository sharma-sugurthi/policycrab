"""
Agent 4: Explanation — Cross-cutting agent that translates
technical insurance output into patient-friendly plain English.

This agent is called AFTER each major pipeline phase to provide
the patient with a clear, actionable explanation of what happened.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.services.llm_router import get_llm, TaskType
from app.models.policy import PolicyProfile
from app.models.claim import ClaimCase, CostBreakdown
from app.models.appeal import AppealOutput

logger = logging.getLogger(__name__)

EXPLANATION_SYSTEM_PROMPT = """You are a patient advocate who explains health insurance decisions 
in plain, clear English. The patient has NO insurance expertise.

Rules:
1. Be accurate — never change the meaning or omit critical financial details
2. Use short, direct sentences. Avoid jargon. Avoid passive voice.
3. Show dollar amounts clearly: "You owe $700 — here's why: $500 goes to your deductible, 
   and $200 is your 20% share of the remaining cost."
4. For deadlines, state BOTH the exact date AND how many days are left
5. Frame legal rights as actions: "You have the right to appeal" → "You CAN appeal this. Here's how:"
6. End with 2-3 specific, numbered next steps
7. Speak directly to the patient: use "you" and "your"
8. Do NOT add information that isn't in the data provided
9. Keep the total explanation under 300 words
"""


async def explanation_node(state: AgentState) -> dict:
    """
    Generate plain-English explanations for the current pipeline phase.
    """
    phase = state.get("current_phase", "unknown")
    explanations = dict(state.get("explanations", {}))
    logger.info(f"Agent 4 (Explanation): Explaining phase '{phase}'")

    try:
        llm = get_llm(TaskType.EXPLANATION, temperature=0.3)

        # Build context based on current phase
        if phase == "ingestion" and state.get("policy_profile"):
            policy = PolicyProfile(**state["policy_profile"])
            
            # Guard all Optional enum/numeric fields — the LLM may not extract them
            plan_type_str = policy.plan_type.value if policy.plan_type else "Unknown"
            legal_class_str = policy.legal_classification.value if policy.legal_classification else "Unknown"
            deductible_str = f"${policy.in_network_deductible_individual:,.2f}" if policy.in_network_deductible_individual is not None else "N/A"
            oop_max_str = f"${policy.in_network_oop_max_individual:,.2f}" if policy.in_network_oop_max_individual is not None else "N/A"
            
            if policy.in_network_coinsurance is not None:
                coinsurance_str = (
                    f"{policy.in_network_coinsurance * 100:.0f}% patient / "
                    f"{(1 - policy.in_network_coinsurance) * 100:.0f}% insurer"
                )
            else:
                coinsurance_str = "N/A"
            
            technical = (
                f"Policy parsed: {policy.plan_name} by {policy.carrier_name}\n"
                f"Type: {plan_type_str} | Classification: {legal_class_str}\n"
                f"Deductible: {deductible_str}\n"
                f"OOP Max: {oop_max_str}\n"
                f"Coinsurance: {coinsurance_str}\n"
                f"Requires PCP Referral: {policy.requires_pcp_referral}\n"
                f"HSA Eligible: {policy.is_hsa_eligible}"
            )

        elif phase in ("calculation", "intake") and state.get("cost_breakdown"):
            cost = CostBreakdown(**state["cost_breakdown"])
            claim = ClaimCase(**state["claim_case"]) if state.get("claim_case") else None
            technical = (
                f"Claim: {claim.cpt_description if claim else 'Unknown'}\n"
                f"Status: {cost.claim_status.value}\n"
                f"Billed: ${cost.billed_amount:,.2f} | Allowed: ${cost.allowed_amount:,.2f}\n"
                f"Applied to deductible: ${cost.applied_to_deductible:,.2f}\n"
                f"Coinsurance: ${cost.coinsurance_amount:,.2f}\n"
                f"Your total responsibility: ${cost.total_patient_responsibility:,.2f}\n"
                f"Insurance pays: ${cost.total_insurer_payout:,.2f}\n"
                f"OOP Max hit: {cost.hit_oop_max}\n"
                f"Notes: {'; '.join(cost.calculation_notes)}"
            )
            if cost.denial_reason:
                technical += f"\nDenial reason: {cost.denial_reason.value}"

        elif phase == "appeal" and state.get("appeal_output"):
            appeal = AppealOutput(**state["appeal_output"])
            technical = (
                f"Appeal Framework: {appeal.appeal_framework.value}\n"
                f"Denial Reason: {appeal.denial_reason.value}\n"
                f"Deadline: {appeal.appeal_deadline.isoformat()} "
                f"({appeal.days_remaining} days remaining)\n"
                f"Regulations cited: {len(appeal.cited_regulations)}\n"
                f"Next steps: {'; '.join(appeal.recommended_next_steps)}"
            )
        else:
            logger.warning(f"Agent 4: No data available for phase '{phase}'")
            return {"explanations": explanations, "current_phase": phase}

        messages = [
            SystemMessage(content=EXPLANATION_SYSTEM_PROMPT),
            HumanMessage(content=f"Explain this to the patient:\n\n{technical}"),
        ]

        response = await llm.ainvoke(messages)
        explanations[phase] = response.content

        # If we're explaining an appeal, also update the appeal_output
        if phase == "appeal" and state.get("appeal_output"):
            appeal_data = dict(state["appeal_output"])
            appeal_data["plain_english_summary"] = response.content
            return {
                "explanations": explanations,
                "appeal_output": appeal_data,
                "current_phase": phase,
            }

        logger.info(f"Agent 4: Explanation generated for phase '{phase}' ({len(response.content)} chars)")

        return {
            "explanations": explanations,
            "current_phase": phase,
        }

    except Exception as e:
        error_msg = f"Agent 4: Explanation generation failed: {e}"
        logger.error(error_msg)
        explanations[phase] = f"(Explanation unavailable: {e})"
        return {
            "explanations": explanations,
            "errors": state.get("errors", []) + [error_msg],
            "current_phase": phase,
        }
