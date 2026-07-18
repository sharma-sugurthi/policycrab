"""
Agent 4 (New): Policy Analyzer — Deep contradiction detection.

This agent is the core of PolicyCrab's 10/10 capability.
It performs structured legal reasoning over the patient's actual
insurance policy document, finding places where the insurer's
denial reason contradicts the policy's own written language.

Pipeline:
  1. Build denial-targeted search queries from the ClaimCase.
  2. Semantic search the patient's policy chunks in Supabase.
  3. Run Gemini Pro to compare denial reason vs. policy language.
  4. Output structured ContradictionAnalysis with exact page citations.
  5. Determine an honest appeal strength (WIN / UNLIKELY / INCORRECT_DENIAL).

This agent runs AFTER cost_calculation and BEFORE grievance.
Its output is injected directly into the grievance prompt so the
appeal letter can cite exact page numbers from the patient's policy.
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.services.llm_router import get_llm, TaskType, generate_embedding
from app.services.supabase_client import search_policy_document
from app.models.claim import ClaimCase
from app.models.policy import PolicyProfile
from app.models.enums import DenialReason

logger = logging.getLogger(__name__)


# ── Denial-to-Query mapping ───────────────────────────────────────
# These targeted queries maximize the chance of finding the exact
# policy clause that contradicts the insurer's denial.
DENIAL_QUERIES: dict[str, list[str]] = {
    DenialReason.PRIOR_AUTH_MISSING.value: [
        "prior authorization requirements emergency services",
        "prior authorization waiver emergency admission",
        "preauthorization not required emergency",
        "prior approval required procedures list",
    ],
    DenialReason.MEDICAL_NECESSITY.value: [
        "medical necessity definition criteria",
        "medically necessary services coverage",
        "clinical necessity review criteria",
        "experimental investigational exclusion definition",
    ],
    DenialReason.NOT_COVERED.value: [
        "covered services benefits summary",
        "exclusions not covered services list",
        "benefit limitations exceptions",
        "essential health benefits covered",
    ],
    DenialReason.OUT_OF_NETWORK_DENIAL.value: [
        "out of network coverage emergency",
        "out of network benefits emergency services",
        "balance billing surprise billing protections",
        "network exception criteria",
    ],
    DenialReason.TIMELY_FILING.value: [
        "timely filing deadline claim submission",
        "filing deadline exceptions appeal",
        "claim submission time limit",
    ],
    DenialReason.REFERRAL_MISSING.value: [
        "referral requirements specialist",
        "primary care physician referral waiver",
        "self referral specialist access",
    ],
    DenialReason.PRE_EXISTING_CONDITION.value: [
        "pre-existing condition exclusion",
        "waiting period pre-existing condition",
        "ACA pre-existing condition prohibition",
    ],
    DenialReason.COB_FAILURE.value: [
        "coordination of benefits primary secondary",
        "other insurance coordination rules",
    ],
}

_DEFAULT_QUERIES = [
    "coverage exclusions limitations",
    "covered benefits services",
    "appeal rights grievance process",
    "denial reason justification",
]


CONTRADICTION_ANALYSIS_PROMPT = """You are a senior health insurance attorney specializing in
patient rights and wrongful claim denials. Your job is to perform a rigorous legal analysis
of whether the insurer's stated denial reason is supported or CONTRADICTED by the patient's
own insurance policy document.

You will be provided:
1. DENIAL INFORMATION: The specific reason the insurer gave for denying the claim.
2. POLICY CLAUSES: Relevant excerpts retrieved from the patient's actual policy document,
   each with an exact page number.

YOUR TASK:
Analyze whether the denial reason is consistent with or contradicted by the policy language.

Output a JSON object with this EXACT structure:
{
  "is_contradiction": true/false,
  "contradiction_strength": "STRONG" | "MODERATE" | "WEAK" | "NONE",
  "appeal_recommendation": "STRONG_APPEAL" | "APPEAL" | "EXCEPTION_REQUEST" | "UNLIKELY_TO_WIN" | "CLAIM_CORRECTLY_DENIED",
  "appeal_strength_rationale": "One sentence explaining the overall recommendation",
  "contradictions": [
    {
      "page_number": 47,
      "exact_clause_text": "The exact text from the policy that contradicts the denial",
      "denial_basis": "What the insurer claimed as the reason",
      "contradiction_explanation": "Precise legal explanation of how this clause contradicts the denial",
      "insurer_mistake": "Concise description of the specific error the insurer made"
    }
  ],
  "supporting_clauses": [
    {
      "page_number": 12,
      "exact_clause_text": "Text that SUPPORTS the insurer's position",
      "how_it_supports_denial": "Explanation"
    }
  ],
  "key_findings": [
    "Finding 1: Concise, factual statement about what the policy says",
    "Finding 2: Another factual finding"
  ],
  "honest_assessment": "A blunt, honest 2-3 sentence assessment. If the denial is valid, say so clearly. If it is wrongful, explain exactly why. Patients need honesty, not false hope."
}

CRITICAL RULES:
- NEVER fabricate page numbers or clause text. Only cite exactly what is in the provided excerpts.
- If no contradictions exist, set is_contradiction=false and appeal_recommendation="CLAIM_CORRECTLY_DENIED".
- Be honest. If the patient is unlikely to win, say so. False appeals waste months of a patient's life.
- Provide exact verbatim quotes from the policy text, not paraphrases.

EDGE CASE GUIDANCE (STRICT):
1. **Emergency vs Prior Auth**: If it's an emergency (e.g. appendicitis) and the policy says emergency surgery is covered, but denial is "No prior authorization", this is a WRONG DENIAL. Recommend STRONG_APPEAL.
2. **Explicit Exclusions**: If a procedure (e.g. cosmetic surgery out-of-network) is explicitly excluded in the policy, DO NOT recommend an appeal. Output CLAIM_CORRECTLY_DENIED.
3. **Annual Limits**: If the patient exceeded an annual monetary or visit limit stated in the policy, detect this and output CLAIM_CORRECTLY_DENIED (annual maximum reached).
4. **Formulary Exceptions**: If a necessary medication (e.g. for diabetes) is denied because it isn't on the formulary, do NOT recommend a standard appeal. Recommend EXCEPTION_REQUEST.
5. **Hard Exclusions (e.g. IVF/Infertility)**: If the policy explicitly excludes a service like infertility, output UNLIKELY_TO_WIN or CLAIM_CORRECTLY_DENIED and be completely honest that appealing is a waste of time. Trust requires honesty."""


async def policy_analyzer_node(state: AgentState) -> dict:
    """
    Deep contradiction detection: compares the denial reason against the
    patient's own policy document clauses retrieved from Supabase.

    Runs AFTER cost_calculation, BEFORE grievance.
    """
    logger.info("Agent 4 (Policy Analyzer): Starting deep contradiction analysis")

    errors = state.get("errors", [])
    session_id = state.get("session_id")
    benchmark_excerpt = state.get("benchmark_policy_excerpt")
    
    if benchmark_excerpt:
        policy_indexed = True
        logger.info("Agent 4: Benchmark mode active. Bypassing RAG and injecting mock policy excerpt.")
    else:
        policy_indexed = state.get("policy_indexed", False)

    if (not session_id and not benchmark_excerpt) or not policy_indexed:
        # No policy document was indexed — skip and let grievance use regulations only
        logger.warning(
            "Agent 4: No indexed policy document found. "
            "Skipping document-level analysis. Grievance will use regulations only."
        )
        return {
            "contradiction_analysis": None,
            "current_phase": "analysis",
            "errors": errors,
        }

    if not state.get("claim_case"):
        return {
            "contradiction_analysis": None,
            "current_phase": "analysis",
            "errors": errors + ["Policy Analyzer: No claim case available"],
        }

    try:
        claim = ClaimCase(**state["claim_case"])
        policy = PolicyProfile(**state["policy_profile"]) if state.get("policy_profile") else None

        denial_reason = claim.denial_reason or DenialReason.OTHER

        # ── Step 1: Build targeted queries ───────────────────────────
        targeted_queries = DENIAL_QUERIES.get(denial_reason.value, _DEFAULT_QUERIES)

        # Add claim-specific context queries
        if claim.cpt_description:
            targeted_queries.append(f"{claim.cpt_description} coverage requirements")
        if claim.icd_10_description:
            targeted_queries.append(f"{claim.icd_10_description} covered diagnosis")
        if claim.is_emergency:
            targeted_queries.append("emergency services coverage prior authorization waiver")

        logger.info(f"Agent 4: Searching policy document with {len(targeted_queries)} queries")

        if benchmark_excerpt:
            policy_excerpts = f"[PAGE 1 (BENCHMARK INJECTION)]\n{benchmark_excerpt}"
            all_results = [{"page_number": 1, "chunk_text": benchmark_excerpt}]
            targeted_queries = ["benchmark"]
        else:
            # ── Step 2: Retrieve relevant policy chunks ───────────────────
            all_results: list[dict] = []
            seen_pages: set[int] = set()

            for query in targeted_queries[:6]:  # Limit to top 6 queries
                embedding = await generate_embedding(query)
                results = await search_policy_document(
                    session_id=session_id,
                    query_embedding=embedding,
                    match_count=4,
                    similarity_threshold=0.25,  # Lower threshold for policy docs (specialized language)
                )
                for r in results:
                    page_key = (r["page_number"], r["chunk_index"])
                    if page_key not in seen_pages:
                        seen_pages.add(page_key)
                        all_results.append(r)

            if not all_results:
                logger.warning(
                    "Agent 4: No relevant policy clauses found in vector store. "
                    "This may indicate the policy was not indexed or similarity threshold is too high."
                )
                return {
                    "contradiction_analysis": {
                        "is_contradiction": False,
                        "appeal_recommendation": "APPEAL",
                        "appeal_strength_rationale": "No specific policy clauses could be retrieved for analysis. Regulatory-only appeal will be generated.",
                        "contradictions": [],
                        "supporting_clauses": [],
                        "key_findings": ["Policy document could not be analyzed for specific clause contradictions."],
                        "honest_assessment": "Unable to perform document-level analysis. The appeal will be based on federal and state regulations only.",
                        "policy_clauses_searched": len(targeted_queries),
                        "clauses_retrieved": 0,
                    },
                    "current_phase": "analysis",
                    "errors": errors,
                }

            # Sort by page number for logical presentation
            all_results.sort(key=lambda r: (r["page_number"], r.get("chunk_index", 0)))

            # ── Step 3: Build context for the LLM ────────────────────────
            policy_excerpts = "\n\n".join([
                f"[PAGE {r['page_number']}]\n{r['chunk_text']}"
                for r in all_results[:12]  # Top 12 unique chunks
            ])

        denial_context = (
            f"DENIAL INFORMATION:\n"
            f"- Denial Reason: {denial_reason.value}\n"
            f"- CARC Code: {claim.denial_carc_code or 'Not specified'}\n"
            f"- Procedure: CPT {claim.cpt_code} — {claim.cpt_description}\n"
            f"- Diagnosis: ICD-10 {claim.icd_10_code} — {claim.icd_10_description}\n"
            f"- Was Emergency: {claim.is_emergency}\n"
            f"- Network Status: {claim.network_status.value}\n"
            f"- Prior Auth Obtained: {claim.prior_auth_obtained}\n"
            f"- Prior Auth Required (per policy): {claim.prior_auth_required}\n"
        )
        if policy:
            denial_context += (
                f"- Plan Type: {policy.plan_type.value}\n"
                f"- Legal Classification: {policy.legal_classification.value}\n"
            )

        # ── Step 4: Run Gemini Pro for contradiction analysis ─────────
        llm = get_llm(TaskType.REASONING, temperature=0.0)

        messages = [
            SystemMessage(content=CONTRADICTION_ANALYSIS_PROMPT),
            HumanMessage(content=(
                f"{denial_context}\n\n"
                f"POLICY DOCUMENT EXCERPTS (from patient's actual policy):\n"
                f"{policy_excerpts}\n\n"
                f"Perform the contradiction analysis now."
            )),
        ]

        response = await llm.ainvoke(messages)
        content = response.content

        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        analysis_data = json.loads(content.strip())

        # Add metadata
        analysis_data["policy_clauses_searched"] = len(targeted_queries)
        analysis_data["clauses_retrieved"] = len(all_results)
        analysis_data["pages_analyzed"] = sorted({r["page_number"] for r in all_results})

        logger.info(
            f"Agent 4: Analysis complete — "
            f"Contradiction: {analysis_data.get('is_contradiction')}, "
            f"Strength: {analysis_data.get('contradiction_strength')}, "
            f"Recommendation: {analysis_data.get('appeal_recommendation')}, "
            f"Clauses found: {len(all_results)}"
        )

        return {
            "contradiction_analysis": analysis_data,
            "current_phase": "analysis",
            "errors": errors,
        }

    except json.JSONDecodeError as e:
        error_msg = f"Agent 4: Failed to parse contradiction analysis JSON: {e}"
        logger.error(error_msg)
        return {
            "contradiction_analysis": None,
            "current_phase": "analysis",
            "errors": errors + [error_msg],
        }
    except Exception as e:
        error_msg = f"Agent 4: Policy analysis failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "contradiction_analysis": None,
            "current_phase": "analysis",
            "errors": errors + [error_msg],
        }
