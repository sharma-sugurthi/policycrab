"""
Multi-Level Appeal Drafting — POST /api/claim/draft-appeal

Generates a Level 2 (External IRO) or Level 3 (State DOI) appeal letter
from an existing Level 1 denial. Uses a different prompt and addressee
for each level, with level-specific legal grounds.
"""

import json
import logging
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.security.rate_limit import rate_limit_user
from app.services.llm_router import get_llm, TaskType, generate_embedding
from app.services.supabase_client import search_knowledge_base
from app.engine.regulatory_router import route_to_appeal_framework, get_appeal_framework_details
from app.models.policy import PolicyProfile
from app.models.claim import ClaimCase
from app.models.enums import DenialReason

logger = logging.getLogger(__name__)

# Per-user: 3 appeal drafts per 60 seconds
DRAFT_APPEAL_RATE_LIMIT = rate_limit_user("claim:draft_appeal", max_requests=3, window_seconds=60)

router = APIRouter(prefix="/api/claim", tags=["Appeals"])


# ── Level-specific letter configs ────────────────────────────────────
LEVEL_CONFIGS = {
    2: {
        "name": "External Independent Review (IRO)",
        "addressee": "The Independent Review Organization (IRO) / External Review Entity",
        "deadline_days": 4,   # ACA mandates IRO request within 4 months of final internal denial
        "urgency_note": "This is a request for External Independent Review under ACA Section 2719 / PPACA.",
        "letter_format": "external_review",
        "legal_basis": [
            "ACA Section 2719 — External Appeals",
            "45 CFR § 147.136 — Internal Claims and Appeals / External Review",
            "DOL Technical Release 2010-01 — Federal External Review Process",
        ],
        "objective": (
            "Request external independent review of the internal appeal denial. "
            "An IRO must be accredited by URAC or NCQA. The plan is bound by the IRO's decision. "
            "Focus on: clinical necessity evidence, peer-reviewed literature, and why the internal "
            "reviewer's decision was contrary to medical evidence and/or plan terms."
        ),
    },
    3: {
        "name": "State Department of Insurance Complaint",
        "addressee": "State Department of Insurance (DOI) / Commissioner of Insurance",
        "deadline_days": 365,
        "urgency_note": "This is a formal complaint with the State Department of Insurance.",
        "letter_format": "doi_complaint",
        "legal_basis": [
            "State Insurance Code — Unfair Claims Settlement Practices Act",
            "ACA Section 2719 — State External Review Process",
            "NAIC Model Act — Prompt Payment of Claims",
        ],
        "objective": (
            "File a formal complaint with the State DOI alleging unfair claims practices. "
            "Focus on: procedural violations, failure to follow plan terms, bad faith denial, "
            "violations of state prompt payment laws, and request for a market conduct examination."
        ),
    },
}

LEVEL_PROMPT_TEMPLATE = """You are a patient advocacy attorney drafting a Level {level} appeal: {level_name}.

{objective}

LETTER REQUIREMENTS:
1. Address it TO: {addressee}
2. Reference the prior Level 1 internal appeal denial and case history
3. Cite the SPECIFIC legal basis: {legal_basis}
4. For Level 2 (IRO): include medical necessity argument, cite peer-reviewed standards
5. For Level 3 (DOI): frame as unfair claims practices, cite state insurance code violations
6. Be formal, persuasive, and factual — never fabricate citations
7. Include specific relief requested and a response deadline
8. Note: {urgency_note}

Respond with JSON:
{{
  "appeal_letter": "Full letter text",
  "cited_regulations": [{{"statute": "...", "description": "...", "relevance": "..."}}],
  "recommended_next_steps": ["..."]
}}"""


class DraftAppealRequest(BaseModel):
    """Request to draft a Level 2 or 3 appeal letter."""
    level: int = Field(..., ge=2, le=3, description="Appeal level: 2 = IRO, 3 = State DOI")
    policy_profile: dict = Field(..., description="Existing PolicyProfile dict")
    claim_case: dict = Field(..., description="Existing ClaimCase dict")
    level1_denial_summary: str | None = Field(
        None,
        description="Brief summary of why the Level 1 internal appeal was denied (optional but improves quality)"
    )


class DraftAppealResponse(BaseModel):
    success: bool
    level: int
    level_name: str
    appeal_letter: str | None = None
    cited_regulations: list[dict] = []
    recommended_next_steps: list[str] = []
    deadline_date: str | None = None
    errors: list[str] = []


@router.post("/draft-appeal", response_model=DraftAppealResponse)
async def draft_escalated_appeal(
    request: DraftAppealRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(DRAFT_APPEAL_RATE_LIMIT),
):
    """
    Draft a Level 2 (External IRO) or Level 3 (State DOI) appeal letter.

    This endpoint is called after a Level 1 internal appeal has been denied.
    It generates a legally grounded letter targeting the correct escalation authority
    with level-specific arguments and legal citations.
    """
    config = LEVEL_CONFIGS[request.level]
    logger.info(f"Draft Appeal: Level {request.level} — {config['name']}")

    try:
        policy = PolicyProfile(**request.policy_profile)
        claim = ClaimCase(**request.claim_case)
        denial_reason = claim.denial_reason or DenialReason.OTHER

        # ── RAG retrieval ─────────────────────────────────────────
        search_queries = [
            f"external independent review IRO appeal process {denial_reason.value}",
            f"ACA section 2719 external review patient rights",
            f"state department of insurance complaint unfair claims {denial_reason.value}",
        ]

        all_chunks = []
        chunk_ids = set()
        for query in search_queries:
            embedding = await generate_embedding(query)
            results = await search_knowledge_base(query_embedding=embedding, match_count=3)
            for r in results:
                if r["concept_id"] not in chunk_ids:
                    chunk_ids.add(r["concept_id"])
                    all_chunks.append(r)

        rag_context = "\n\n".join([
            f"[{r['concept_id']}] {r['title']}\n{r['full_content']}"
            for r in all_chunks[:6]
        ])

        # ── Build prompt ──────────────────────────────────────────
        framework = route_to_appeal_framework(policy, claim)
        framework_details = get_appeal_framework_details(framework)

        deadline = (date.today() + timedelta(days=config["deadline_days"])).isoformat()

        system_prompt = LEVEL_PROMPT_TEMPLATE.format(
            level=request.level,
            level_name=config["name"],
            addressee=config["addressee"],
            objective=config["objective"],
            legal_basis=", ".join(config["legal_basis"]),
            urgency_note=config["urgency_note"],
        )

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
            f"- Denial Reason: {denial_reason.value}\n"
            f"- CARC Code: {claim.denial_carc_code or 'Not specified'}\n"
            f"- Appeal Framework: {framework.value}\n"
            f"- Governing Law: {framework_details.get('governing_law', 'N/A')}\n"
        )
        if request.level1_denial_summary:
            case_summary += f"\nLEVEL 1 DENIAL SUMMARY:\n{request.level1_denial_summary}\n"

        # ── LLM call ──────────────────────────────────────────────
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = get_llm(TaskType.LEGAL_WRITING, temperature=0.3)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=(
                f"{case_summary}\n\n"
                f"RETRIEVED REGULATORY KNOWLEDGE:\n{rag_context}\n\n"
                f"Draft the Level {request.level} appeal letter now."
            )),
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
                    f"Send this Level {request.level} appeal to: {config['addressee']}",
                    f"File before: {deadline}",
                ],
            }

        logger.info(f"Draft Appeal: Level {request.level} complete — "
                    f"{len(appeal_data.get('cited_regulations', []))} citations")

        return DraftAppealResponse(
            success=True,
            level=request.level,
            level_name=config["name"],
            appeal_letter=appeal_data.get("appeal_letter", ""),
            cited_regulations=appeal_data.get("cited_regulations", []),
            recommended_next_steps=appeal_data.get("recommended_next_steps", []),
            deadline_date=deadline,
        )

    except Exception as e:
        logger.error(f"Draft Appeal Level {request.level} failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Appeal drafting failed: {str(e)}")
