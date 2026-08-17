"""
Agent 3: Grievance & Appeals — Drafts formal appeal letters for
denied claims using RAG-powered legal citations.

This is the highest-quality agent, using Gemini Pro for persuasive
legal writing. It retrieves relevant regulations from the knowledge
base and constructs a formal, legally grounded appeal letter.
"""

import json
import logging
import re
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
from app.engine.carrier_intelligence import get_carrier_intelligence, format_carrier_intelligence_for_prompt

logger = logging.getLogger(__name__)

CARC_PRECEDENTS = {
    "CO-50": "Medical Necessity denial. Cite: ERISA Sec. 503 (29 CFR § 2560.503-1). Requires the plan to provide the specific rule, guideline, or protocol used in the denial, and mandates a 'full and fair review' by an independent medical professional.",
    "PR-96": "Non-covered charge / Experimental denial. Cite: Affordable Care Act (ACA) § 2719. Requires plans to ensure coverage for essential health benefits and allows external review for medical judgement denials.",
    "CO-16": "Lack of Information. Cite: ERISA Sec. 503. The plan must provide a specific description of any additional material or information necessary to perfect the claim and an explanation of why it is necessary.",
    "CO-22": "Coordination of Benefits (COB). Cite: NAIC Coordination of Benefits Model Regulation (if state-regulated) to argue proper primary/secondary payer determination.",
    "CO-45": "Charge exceeds fee schedule/UCR. If out-of-network, cite: No Surprises Act (NSA) for emergency services or covered non-emergency services at in-network facilities, protecting the patient from balance billing.",
}

APPEAL_DRAFTING_PROMPT = """You are a patient advocacy attorney specializing in US health insurance 
appeals. Draft a formal appeal letter for the denied claim described below.

LETTER REQUIREMENTS:
1. Use formal business letter format
2. Address it to the plan's grievance/appeals department
3. Reference the specific denial reason and any CARC/RARC codes
4. If POLICY CONTRADICTIONS are provided below, cite them with EXACT PAGE NUMBERS (e.g., 'As stated on Page 47 of the attached policy...'). This is mandatory.
5. Cite the SPECIFIC federal/state regulations that support the patient's case
6. Use the regulatory citations from the knowledge base retrieval (provided below)
7. Include a clear statement of what relief is being requested
8. Reference relevant legal precedents and statutes
9. Include a deadline for the plan to respond
10. Be persuasive but factual — never fabricate citations, page numbers, or clause text
11. End with consequences of non-compliance (DOI complaint, federal court, etc.)
12. If the denial reason is MENTAL_HEALTH_PARITY, the letter MUST include a formal request for a Comparative Analysis of Non-Quantitative Treatment Limitations (NQTLs) as required by the Mental Health Parity and Addiction Equity Act (MHPAEA). Demand the plan prove that its criteria for mental health are no more stringent than for medical/surgical benefits.
13. If the denial reason is FORMULARY_EXCLUSION or STEP_THERAPY_REQUIRED, the letter MUST explicitly request a "Formulary Exception" under 45 CFR 156.122(c) (for ACA plans) or standard medical necessity exception, noting that the prescribing physician deems the requested drug clinically necessary and/or that step therapy alternatives are contraindicated.
14. If the plan classification is INDIVIDUAL_ACA, the letter MUST explicitly cite 45 CFR § 147.136 for internal appeal/external review rights and, if a core service was denied, cite 45 CFR § 156.110 (Essential Health Benefits) prohibiting pre-existing condition exclusions and lifetime limits.
15. If the HONEST ASSESSMENT indicates the patient is unlikely to win, still write the letter but include a note in recommended_next_steps about the realistic prospects

CRITICAL: When policy contradictions are available, the letter must include a section titled
'SPECIFIC POLICY CONTRADICTIONS' that states verbatim: 'On page [X] of the policy, it states:
[exact quote]. The insurer's denial of [reason] directly contradicts this provision.'

REGULATORY CONTEXT: Use the retrieved knowledge base excerpts to cite specific laws, 
deadlines, and patient rights. Every legal assertion must be supported by a citation.

Respond with a JSON object containing:
- appeal_letter: The full text of the appeal letter
- cited_regulations: Array of objects with {statute, description, relevance}
- recommended_next_steps: Array of specific actionable steps for the patient
"""


PROVIDER_CORRECTION_PROMPT = """You are a medical billing advocate helping a patient request a
corrected claim resubmission from a hospital's billing department.

The insurance claim was DENIED due to a PROVIDER BILLING ERROR — not because of a coverage issue.
The hospital's billing department needs to correct and refile the claim.

Draft a professional, clear letter to the HOSPITAL BILLING DEPARTMENT (NOT the insurance company)
requesting a corrected claim resubmission.

LETTER REQUIREMENTS:
1. Address it to 'Patient Billing Department' or 'Medical Billing Office'
2. Clearly identify the claim: patient name, date of service, claim/account number if known
3. State the specific billing errors detected (from the triage analysis)
4. Reference the CARC denial code and its meaning
5. Request a specific corrective action (e.g., 'add Modifier 25 to CPT code XXXXX')
6. Request a written confirmation of resubmission
7. Set a 30-day response deadline
8. Be firm but professional — this is not adversarial, it's a correction request
9. Do NOT cite ERISA or ACA — this is a billing correction, not a legal appeal

Respond with a JSON object containing:
- appeal_letter: The full text of the corrected claim request letter
- cited_regulations: [] (empty — no regulations needed for billing corrections)
- recommended_next_steps: Array of specific actionable steps for the patient
"""


async def grievance_node(state: AgentState) -> dict:
    """
    Draft a formal letter for a denied claim.
    """
    if state.get("claim_overrides"):
        logger.info("Agent 3 (Grievance): Benchmark mode detected — bypassing LLM letter generation.")
        contra = state.get("contradiction_analysis") or {}
        triage = state.get("triage_decision") or {}
        return {
            "appeal_output": {
                "appeal_letter": "[BENCHMARK MODE] Legal appeal letter drafting bypassed for evaluation efficiency.",
                "legal_citations": [],
                "next_steps": ["Submit appeal to carrier or provider"],
                "contradiction_detected": contra.get("is_contradiction", False),
                "contradiction_strength": contra.get("contradiction_strength", "NONE"),
                "appeal_recommendation": contra.get("appeal_recommendation", "UNKNOWN"),
                "triage_path": triage.get("path"),
                "estimated_success_probability": triage.get("estimated_success_probability", 0.5),
            },
            "current_phase": "appeal",
            "errors": state.get("errors", []),
        }

    errors = state.get("errors", [])
    triage_decision = state.get("triage_decision")

    # ── Route based on Triage Agent decision ──────────────────────
    triage_path = "PAYER_ILLEGAL_DENIAL"  # default — never block the appeal path
    triage_confidence = "LOW"
    triage_action_summary = ""
    estimated_success_probability = 0.5

    if triage_decision:
        triage_path = triage_decision.get("path", "PAYER_ILLEGAL_DENIAL")
        triage_confidence = triage_decision.get("confidence", "LOW")
        triage_action_summary = triage_decision.get("action_summary", "")
        estimated_success_probability = triage_decision.get("estimated_success_probability", 0.5)

    if triage_path == "PROVIDER_CODING_ERROR":
        logger.info(
            "Agent 3 (Grievance): Triage → PROVIDER_CODING_ERROR. "
            "Drafting corrected claim request letter to provider billing department."
        )
        return await _draft_provider_correction_letter(
            state, errors, triage_decision,
            triage_path, triage_confidence, triage_action_summary, estimated_success_probability
        )
    else:
        logger.info(
            f"Agent 3 (Grievance): Triage → {triage_path} (confidence={triage_confidence}). "
            "Drafting formal legal appeal letter to insurance company."
        )
        return await _draft_payer_appeal_letter(
            state, errors, triage_decision,
            triage_path, triage_confidence, triage_action_summary, estimated_success_probability
        )


async def _draft_provider_correction_letter(
    state: AgentState,
    errors: list,
    triage_decision: dict,
    triage_path: str,
    triage_confidence: str,
    triage_action_summary: str,
    estimated_success_probability: float,
) -> dict:
    """
    Draft a corrected claim request letter to the hospital's billing department.
    This is the PROVIDER_CODING_ERROR path — no ERISA citations, no RAG retrieval.
    """
    if not state.get("claim_case"):
        return {"errors": errors + ["Grievance Agent: No claim case available"], "current_phase": "appeal"}

    try:
        claim = ClaimCase(**state["claim_case"])
        policy = PolicyProfile(**state["policy_profile"]) if state.get("policy_profile") else None

        framework = route_to_appeal_framework(policy, claim) if policy else None
        denial_date = claim.denial_date or date.today()

        coding_errors = triage_decision.get("coding_errors_detected", []) if triage_decision else []
        corrected_claim_instructions = triage_decision.get("corrected_claim_instructions", "") if triage_decision else ""

        case_summary = (
            f"CLAIM DETAILS (for corrected claim request):\n"
            f"- Patient Plan: {policy.plan_name if policy else 'Unknown'} ({policy.carrier_name if policy else ''})\n"
            f"- Procedure: CPT {claim.cpt_code} — {claim.cpt_description}\n"
            f"- Diagnosis: ICD-10 {claim.icd_10_code} — {claim.icd_10_description}\n"
            f"- Date of Service: {claim.date_of_service}\n"
            f"- Billed Amount: ${claim.billed_amount:,.2f}\n"
            f"- Provider: {claim.provider_name or 'Not specified'}\n"
            f"- Facility: {claim.facility_name or 'Not specified'}\n"
            f"- Denial CARC Code: {claim.denial_carc_code or 'Not specified'}\n"
            f"\nCODING ERRORS DETECTED BY TRIAGE ANALYSIS:\n"
        )
        for err in coding_errors:
            case_summary += f"• {err}\n"

        if corrected_claim_instructions:
            case_summary += f"\nSUGGESTED CORRECTIVE ACTIONS:\n{corrected_claim_instructions}\n"

        llm = get_llm(TaskType.LEGAL_WRITING, temperature=0.3)
        messages = [
            SystemMessage(content=PROVIDER_CORRECTION_PROMPT),
            HumanMessage(content=f"{case_summary}\n\nDraft the provider correction request letter now."),
        ]

        response = await llm.ainvoke(messages)
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            appeal_data = json.loads(content.strip())
        except json.JSONDecodeError:
            appeal_data = {
                "appeal_letter": response.content,
                "cited_regulations": [],
                "recommended_next_steps": [
                    "Send this letter to the hospital's billing department via certified mail.",
                    "Follow up in 30 days if no response.",
                    "Request written confirmation of corrected claim resubmission.",
                ],
            }

        appeal_output = AppealOutput(
            appeal_framework=framework if framework else route_to_appeal_framework(
                PolicyProfile(
                    plan_name="Unknown", carrier_name="Unknown",
                    plan_type="PPO", legal_classification="FULLY_INSURED",
                ) if not policy else policy,
                claim,
            ),
            denial_reason=claim.denial_reason or DenialReason.OTHER,
            denial_date=denial_date,
            appeal_deadline=denial_date,  # No legal deadline for correction requests
            days_remaining=30,
            appeal_letter=appeal_data.get("appeal_letter", ""),
            letter_type="provider_correction",
            letter_format="correction_request",
            cited_regulations=[],
            cited_knowledge_chunks=[],
            policy_citations=[],
            contradiction_detected=False,
            contradiction_strength="NONE",
            appeal_recommendation="PROVIDER_CORRECTION",
            honest_assessment=triage_action_summary,
            plain_english_summary="",
            recommended_next_steps=appeal_data.get("recommended_next_steps", []),
            triage_path=triage_path,
            triage_confidence=triage_confidence,
            triage_action_summary=triage_action_summary,
            estimated_success_probability=estimated_success_probability,
        )

        logger.info(
            f"Agent 3 (Grievance): Provider correction letter drafted. "
            f"Coding errors: {len(coding_errors)}. "
            f"Estimated success: {estimated_success_probability:.0%}"
        )

        return {
            "appeal_output": appeal_output.model_dump(mode="json"),
            "current_phase": "appeal",
            "errors": errors,
        }

    except Exception as e:
        error_msg = f"Agent 3 (Provider Correction): Letter drafting failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {"errors": errors + [error_msg], "current_phase": "appeal"}


async def _draft_payer_appeal_letter(
    state: AgentState,
    errors: list,
    triage_decision: dict | None,
    triage_path: str,
    triage_confidence: str,
    triage_action_summary: str,
    estimated_success_probability: float,
) -> dict:
    """
    Draft a formal legal appeal letter to the insurance company.
    This is the original PAYER_ILLEGAL_DENIAL path — full ERISA/ACA/NSA legal writing.
    """
    logger.info("Agent 3 (Grievance): Starting payer appeal letter drafting")

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

        if denial_reason == DenialReason.MENTAL_HEALTH_PARITY:
            search_queries.append("MHPAEA Mental Health Parity and Addiction Equity Act NQTL non-quantitative treatment limitation violation")
        elif denial_reason == DenialReason.FORMULARY_EXCLUSION:
            search_queries.append("formulary exception request ACA 45 CFR 156.122 non-formulary drug appeal")
        elif denial_reason == DenialReason.STEP_THERAPY_REQUIRED:
            search_queries.append("step therapy exception fail first protocol override appeal")

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
        )
        
        # Inject CARC-specific legal precedent if available
        if claim.denial_carc_code and claim.denial_carc_code.upper() in CARC_PRECEDENTS:
            precedent = CARC_PRECEDENTS[claim.denial_carc_code.upper()]
            case_summary += f"- CARC Precedent to Cite: {precedent}\n"

        case_summary += (
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

        # ── Step 4a-bis: Inject Insurer-Specific Intelligence ─────────
        carrier_intel = get_carrier_intelligence(policy.carrier_name)
        if carrier_intel:
            case_summary += format_carrier_intelligence_for_prompt(carrier_intel) + "\n"

        # ── Step 4b: Inject Policy Contradiction Evidence ─────────────
        # This is the key upgrade: if the Policy Analyzer found contradictions,
        # inject the exact page numbers and clause text into the letter prompt.
        contradiction_context = ""
        contradiction_analysis = state.get("contradiction_analysis")
        appeal_recommendation = "APPEAL"  # default
        contradiction_detected = False
        contradiction_strength = "NONE"
        honest_assessment = ""
        policy_citations_for_output = []

        if contradiction_analysis:
            appeal_recommendation = contradiction_analysis.get("appeal_recommendation", "APPEAL")
            contradiction_detected = contradiction_analysis.get("is_contradiction", False)
            contradiction_strength = contradiction_analysis.get("contradiction_strength", "NONE")
            honest_assessment = contradiction_analysis.get("honest_assessment", "")

            contradictions = contradiction_analysis.get("contradictions", [])
            key_findings = contradiction_analysis.get("key_findings", [])

            if contradictions:
                contradiction_context = "\nPOLICY DOCUMENT CONTRADICTIONS (CITE THESE WITH EXACT PAGE NUMBERS):\n"
                for c in contradictions:
                    pg = c.get("page_number", "?")
                    clause = c.get("exact_clause_text", "")
                    explanation = c.get("contradiction_explanation", "")
                    mistake = c.get("insurer_mistake", "")
                    contradiction_context += (
                        f"\n• PAGE {pg}: \"{clause}\"\n"
                        f"  CONTRADICTION: {explanation}\n"
                        f"  INSURER MISTAKE: {mistake}\n"
                    )
                    # Build PolicyCitation for AppealOutput
                    policy_citations_for_output.append({
                        "page_number": pg,
                        "exact_clause_text": clause,
                        "contradiction_explanation": explanation,
                        "insurer_mistake": mistake,
                    })

            if key_findings:
                contradiction_context += "\nKEY FINDINGS FROM POLICY ANALYSIS:\n"
                for finding in key_findings:
                    contradiction_context += f"• {finding}\n"

            if honest_assessment:
                contradiction_context += f"\nHONEST ASSESSMENT: {honest_assessment}\n"

        messages = [
            SystemMessage(content=APPEAL_DRAFTING_PROMPT),
            HumanMessage(content=(
                f"{case_summary}\n\n"
                f"{contradiction_context}\n"
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

        _json_parse_ok = False
        try:
            appeal_data = json.loads(content.strip())
            _json_parse_ok = True
        except json.JSONDecodeError:
            # First try: extract just the cited_regulations array via regex
            # Gemini sometimes produces valid JSON but wraps it in extra prose.
            rescued_citations = []
            cite_match = re.search(
                r'"cited_regulations"\s*:\s*(\[.*?\])',
                response.content,
                re.DOTALL,
            )
            if cite_match:
                try:
                    rescued_citations = json.loads(cite_match.group(1))
                except json.JSONDecodeError:
                    pass

            # Second try: find the letter text directly
            letter_match = re.search(
                r'"appeal_letter"\s*:\s*"(.*?)"\s*[,}]',
                response.content,
                re.DOTALL,
            )
            rescued_letter = ""
            if letter_match:
                try:
                    # Use json.loads on a minimal fragment to handle escape sequences
                    rescued_letter = json.loads('"' + letter_match.group(1) + '"')
                except (json.JSONDecodeError, ValueError):
                    pass

            appeal_data = {
                "appeal_letter": rescued_letter or response.content,
                "cited_regulations": rescued_citations,
                "recommended_next_steps": [
                    "Send this letter via certified mail to the plan's appeals department",
                    f"File before the deadline: {deadline_info['deadline_date']}",
                ],
            }
            if rescued_citations:
                logger.info(
                    f"Agent 3 (Grievance): JSON parse failed but rescued "
                    f"{len(rescued_citations)} citation(s) via regex fallback."
                )
            else:
                logger.warning(
                    "Agent 3 (Grievance): JSON parse failed and citation rescue returned 0 results. "
                    "Check Gemini response format."
                )

        # Build RegulatoryCitation objects
        citations = []
        for reg in appeal_data.get("cited_regulations", []):
            if isinstance(reg, dict):
                citations.append(RegulatoryCitation(
                    statute=reg.get("statute", "Unknown"),
                    description=reg.get("description", ""),
                    relevance=reg.get("relevance", ""),
                ))

        # Fallback: when Gemini returned valid JSON but left cited_regulations=[]
        # despite having been given RAG chunks, synthesize citations from the
        # retrieved knowledge-base entries so AppealOutput always reflects what
        # was consulted. NOT triggered when JSON parse itself failed — in that
        # path the whole response is unreliable and we trust the regex rescue.
        if _json_parse_ok and not citations and all_chunks:
            for chunk in all_chunks[:5]:
                citations.append(RegulatoryCitation(
                    statute=chunk.get("concept_id", chunk.get("title", "Unknown")),
                    description=(chunk.get("semantic_summary") or chunk.get("full_content", ""))[:300],
                    relevance=(
                        f"{chunk.get('domain', 'regulatory')} / "
                        f"{chunk.get('jurisdiction', 'federal')} — "
                        f"retrieved from knowledge base"
                    ),
                ))
            logger.info(
                f"Agent 3 (Grievance): cited_regulations was empty; synthesized "
                f"{len(citations)} citation(s) from the {len(all_chunks)} retrieved RAG chunk(s)."
            )

        # Build PolicyCitation objects from contradiction analysis
        from app.models.appeal import PolicyCitation
        policy_citations = []
        for pc in policy_citations_for_output:
            policy_citations.append(PolicyCitation(
                page_number=pc["page_number"],
                exact_clause_text=pc["exact_clause_text"],
                contradiction_explanation=pc.get("contradiction_explanation", ""),
                insurer_mistake=pc.get("insurer_mistake", ""),
            ))

        appeal_output = AppealOutput(
            appeal_framework=framework,
            denial_reason=denial_reason,
            denial_date=denial_date,
            appeal_deadline=date.fromisoformat(deadline_info["deadline_date"]),
            days_remaining=deadline_info["days_remaining"],
            appeal_letter=appeal_data.get("appeal_letter", ""),
            letter_type="payer_appeal",
            letter_format="formal",
            cited_regulations=citations,
            cited_knowledge_chunks=chunk_ids,
            policy_citations=policy_citations,
            contradiction_detected=contradiction_detected,
            contradiction_strength=contradiction_strength,
            appeal_recommendation=appeal_recommendation,
            honest_assessment=honest_assessment,
            plain_english_summary="",  # Will be populated by Explanation Agent
            recommended_next_steps=appeal_data.get("recommended_next_steps", []),
            triage_path=triage_path,
            triage_confidence=triage_confidence,
            triage_action_summary=triage_action_summary,
            estimated_success_probability=estimated_success_probability,
        )

        logger.info(
            f"Agent 3 (Grievance): Payer appeal drafted. Framework: {framework.value}, "
            f"Deadline: {deadline_info['deadline_date']}, "
            f"Citations: {len(citations)}, RAG chunks: {len(chunk_ids)}. "
            f"Estimated success: {estimated_success_probability:.0%}"
        )

        return {
            "appeal_output": appeal_output.model_dump(mode="json"),
            "current_phase": "appeal",
            "errors": errors,
        }

    except Exception as e:
        error_msg = f"Agent 3 (Payer Appeal): Drafting failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "errors": errors + [error_msg],
            "current_phase": "appeal",
        }
