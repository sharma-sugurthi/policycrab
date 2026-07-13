"""
Agent 3: Grievance & Appeals — Drafts formal appeal letters for
denied claims using RAG-powered legal citations.

This is the highest-quality agent, using Gemini Pro for persuasive
legal writing. It retrieves relevant regulations from the knowledge
base and constructs a formal, legally grounded appeal letter.
"""

import json
import logging
from datetime import date
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.services.llm_router import get_llm, TaskType, generate_embedding
from app.services.supabase_client import search_knowledge_base
from app.engine.regulatory_router import route_to_appeal_framework, get_appeal_framework_details, get_state_enriched_context
from app.engine.deadline_calculator import calculate_appeal_deadline
from app.models.policy import PolicyProfile
from app.models.claim import ClaimCase, CostBreakdown
from app.models.appeal import AppealOutput, RegulatoryCitation
from app.models.enums import DenialReason

logger = logging.getLogger(__name__)

APPEAL_DRAFTING_PROMPT = """You are a patient advocacy attorney specializing in US health insurance 
appeals. Draft a formal appeal letter for the denied claim described below.

LETTER REQUIREMENTS:
1. Use formal business letter format
2. Address it to the plan's grievance/appeals department
3. Reference the specific denial reason and any CARC/RARC codes
4. Cite the SPECIFIC federal/state regulations that support the patient's case
5. Use the regulatory citations from the knowledge base retrieval (provided below)
6. Include a clear statement of what relief is being requested
7. Reference relevant legal precedents and statutes
8. Include a deadline for the plan to respond
9. Be persuasive but factual — never fabricate citations
10. End with consequences of non-compliance (DOI complaint, federal court, etc.)

REGULATORY CONTEXT: Use the retrieved knowledge base excerpts to cite specific laws, 
deadlines, and patient rights. Every legal assertion must be supported by a citation.

Respond with a JSON object containing:
- appeal_letter: The full text of the appeal letter
- cited_regulations: Array of objects with {statute, description, relevance}
- recommended_next_steps: Array of specific actionable steps for the patient
"""


async def grievance_node(state: AgentState) -> dict:
    """
    Draft a formal appeal letter for a denied claim.
    Uses RAG to retrieve relevant regulations, then Gemini Pro for drafting.
    """
    logger.info("Agent 3 (Grievance): Starting appeal letter drafting")

    errors = state.get("errors", [])

    # Validate required inputs
    if not state.get("policy_profile"):
        return {"errors": errors + ["Grievance Agent: No policy profile available"], "current_phase": "appeal"}
    if not state.get("claim_case"):
        return {"errors": errors + ["Grievance Agent: No claim case available"], "current_phase": "appeal"}

    try:
        policy = PolicyProfile(**state["policy_profile"])
        claim = ClaimCase(**state["claim_case"])
        cost = CostBreakdown(**state["cost_breakdown"]) if state.get("cost_breakdown") else None

        # ── Step 1: Determine appeal framework ───────────────────
        framework = route_to_appeal_framework(policy, claim)
        framework_details = get_appeal_framework_details(framework)

        # ── Step 2: Calculate deadline ────────────────────────────
        denial_date = claim.denial_date or date.today()
        deadline_info = calculate_appeal_deadline(
            framework, denial_date, state_code=policy.state
        )

        # ── Step 2b: State-specific regulatory context ────────────
        state_ctx = get_state_enriched_context(policy, framework)

        # ── Step 3: RAG retrieval — get relevant regulations ──────
        denial_reason = claim.denial_reason or (cost.denial_reason if cost else None) or DenialReason.OTHER
        search_queries = [
            f"{denial_reason.value} claim denial appeal rights {framework.value}",
            f"{policy.legal_classification.value} appeal process deadlines",
            f"patient defense strategies against {denial_reason.value} denial",
        ]

        all_chunks = []
        chunk_ids = []
        for query in search_queries:
            embedding = await generate_embedding(query)
            results = await search_knowledge_base(query_embedding=embedding, match_count=3)
            for r in results:
                if r["concept_id"] not in chunk_ids:
                    chunk_ids.append(r["concept_id"])
                    all_chunks.append(r)

        # Format retrieved knowledge for the LLM
        rag_context = "\n\n".join([
            f"[{r['concept_id']}] {r['title']}\n{r['full_content']}"
            for r in all_chunks[:8]  # Limit to top 8 unique chunks
        ])

        # ── Step 4: Draft the appeal letter ───────────────────────
        llm = get_llm(TaskType.LEGAL_WRITING, temperature=0.3)

        case_summary = (
            f"CASE DETAILS:\n"
            f"- Patient's Plan: {policy.plan_name} ({policy.carrier_name})\n"
            f"- Plan Type: {policy.plan_type.value} | Classification: {policy.legal_classification.value}\n"
            f"- State: {policy.state}\n"
            f"- Procedure: CPT {claim.cpt_code} — {claim.cpt_description}\n"
            f"- Diagnosis: ICD-10 {claim.icd_10_code} — {claim.icd_10_description}\n"
            f"- Date of Service: {claim.date_of_service}\n"
            f"- Billed Amount: ${claim.billed_amount:,.2f}\n"
            f"- Network Status: {claim.network_status.value}\n"
            f"- Emergency: {claim.is_emergency}\n"
            f"- NSA Applies: {claim.nsa_applies}\n"
            f"- Denial Reason: {denial_reason.value}\n"
            f"- Denial Date: {denial_date}\n"
            f"- CARC Code: {claim.denial_carc_code or 'Not specified'}\n"
            f"\nAPPEAL FRAMEWORK: {framework.value}\n"
            f"- Governing Law: {framework_details.get('governing_law', 'N/A')}\n"
            f"- Deadline: {deadline_info['deadline_date']} ({deadline_info['days_remaining']} days remaining)\n"
            f"- Urgency: {deadline_info['urgency']}\n"
            f"\nSTATE-SPECIFIC REGULATORY CONTEXT ({policy.state or 'N/A'}):\n"
        )

        # Append state context fields that are relevant
        if state_ctx.get('erisa_preempted'):
            case_summary += f"- {state_ctx['note']}\n"
        else:
            case_summary += (
                f"- External Review Org: {state_ctx.get('external_review_org', 'N/A')}\n"
                f"- External Review Deadline: {state_ctx.get('external_review_deadline_days', 'N/A')} days\n"
                f"- External Review Note: {state_ctx.get('external_review_note', 'N/A')}\n"
            )
            if state_ctx.get('state_surprise_billing_law'):
                case_summary += f"- State Surprise Billing Law: {state_ctx['state_surprise_billing_law']}\n"
                case_summary += f"  Details: {state_ctx['state_surprise_billing_notes']}\n"
            if state_ctx.get('notable_mandates'):
                case_summary += "- Notable State Mandates:\n"
                for m in state_ctx['notable_mandates'][:3]:
                    case_summary += f"  • {m}\n"

        messages = [
            SystemMessage(content=APPEAL_DRAFTING_PROMPT),
            HumanMessage(content=(
                f"{case_summary}\n\n"
                f"RETRIEVED REGULATORY KNOWLEDGE:\n{rag_context}\n\n"
                f"Draft the formal appeal letter now."
            )),
        ]

        response = await llm.ainvoke(messages)
        content = response.content

        # Parse JSON response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            appeal_data = json.loads(content.strip())
        except json.JSONDecodeError:
            # If JSON parsing fails, treat entire response as the letter
            appeal_data = {
                "appeal_letter": response.content,
                "cited_regulations": [],
                "recommended_next_steps": [
                    "Send this letter via certified mail to the plan's appeals department",
                    f"File before the deadline: {deadline_info['deadline_date']}",
                ],
            }

        # Build RegulatoryCitation objects
        citations = []
        for reg in appeal_data.get("cited_regulations", []):
            if isinstance(reg, dict):
                citations.append(RegulatoryCitation(
                    statute=reg.get("statute", "Unknown"),
                    description=reg.get("description", ""),
                    relevance=reg.get("relevance", ""),
                ))

        appeal_output = AppealOutput(
            appeal_framework=framework,
            denial_reason=denial_reason,
            denial_date=denial_date,
            appeal_deadline=date.fromisoformat(deadline_info["deadline_date"]),
            days_remaining=deadline_info["days_remaining"],
            appeal_letter=appeal_data.get("appeal_letter", ""),
            cited_regulations=citations,
            cited_knowledge_chunks=chunk_ids,
            plain_english_summary="",  # Will be populated by Explanation Agent
            recommended_next_steps=appeal_data.get("recommended_next_steps", []),
        )

        logger.info(
            f"Agent 3: Appeal drafted — Framework: {framework.value}, "
            f"Deadline: {deadline_info['deadline_date']}, "
            f"Citations: {len(citations)}, RAG chunks: {len(chunk_ids)}"
        )

        return {
            "appeal_output": appeal_output.model_dump(mode="json"),
            "current_phase": "appeal",
            "errors": errors,
        }

    except Exception as e:
        error_msg = f"Agent 3: Appeal drafting failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "errors": errors + [error_msg],
            "current_phase": "appeal",
        }
