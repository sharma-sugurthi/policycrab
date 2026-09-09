"""
AppealOutput — structured output of the Grievance & Appeals Agent.
Contains the drafted appeal letter, cited regulations, deadlines,
and a plain-English summary from the Explanation Agent.
"""

from datetime import date
from pydantic import BaseModel, Field
from app.models.enums import AppealFramework, DenialReason


class PolicyCitation(BaseModel):
    """A specific clause from the patient's uploaded policy document, cited by exact page number."""
    page_number: int | str | None = Field(None, description="Exact page number in the patient's policy PDF")
    exact_clause_text: str = Field(..., description="Verbatim text from the policy document")
    contradiction_explanation: str = Field(
        "", description="How this clause contradicts the insurer's denial reason"
    )
    insurer_mistake: str = Field(
        "", description="Concise description of the specific error the insurer made"
    )


class RegulatoryCitation(BaseModel):
    """A specific regulation or precedent cited in the appeal letter."""
    statute: str = Field(..., description="e.g., 'ERISA 29 CFR §2560.503-1' or 'ACA Section 2704'")
    description: str = Field(..., description="What this statute mandates or prohibits")
    relevance: str = Field(..., description="Why this applies to the patient's specific case")
    verification_status: str = Field(
        "UNCHECKED",
        description="Set by the appeal_qa citation verifier: 'VERIFIED' | 'UNVERIFIED' | 'UNCHECKED'",
    )
    verification_source: str | None = Field(
        None,
        description="Where the citation was grounded: 'allowlist' | 'kb_chunk' | 'retrieval_text' | None",
    )


# ── Citation Grounding Verification (deterministic, appeal_qa node) ──

class UnverifiedCitation(BaseModel):
    """A regulatory citation the verifier could not ground in a trusted source."""
    statute: str
    reason: str = Field(
        ..., description="'NOT_IN_ALLOWLIST' | 'NOT_IN_RETRIEVED_KB' | 'UNPARSEABLE' | 'UNSOURCED_CARRIER_STAT'"
    )
    kind: str = Field("regulatory", description="'regulatory' | 'policy_clause' | 'inline_letter'")


class UnverifiedPolicyClause(BaseModel):
    """A quoted policy clause that was not found in the retrieved policy chunks."""
    page_number: int | str | None = None
    exact_clause_text: str
    reason: str = Field(
        ..., description="'PAGE_NOT_RETRIEVED' | 'TEXT_NOT_FOUND' | 'PAGE_MISMATCH' | 'LOW_SIMILARITY'"
    )
    best_match_page: int | str | None = None
    best_match_ratio: float | None = None


class CitationVerification(BaseModel):
    """Result of the deterministic citation grounding check."""
    status: str = Field("SKIPPED", description="'VERIFIED' | 'PARTIAL' | 'FAILED' | 'SKIPPED' | 'N/A'")
    verified_count: int = 0
    total_count: int = 0
    unverified: list[UnverifiedCitation] = Field(default_factory=list)
    unverified_policy_clauses: list[UnverifiedPolicyClause] = Field(default_factory=list)
    inline_citations_found: list[str] = Field(
        default_factory=list, description="Statute strings detected in the letter body by regex"
    )
    grounding_score: float = Field(0.0, ge=0.0, le=1.0)
    flags: list[str] = Field(
        default_factory=list,
        description="e.g. 'NO_CITATIONS', 'LETTER_ANNOTATED', 'CITATIONS_STRIPPED', 'ALLOWLIST_NEEDS_HUMAN_VERIFICATION'",
    )
    policy_applied: str = Field("annotate", description="'annotate' | 'strip' | 'off'")
    verifier_version: str = "v1"


class AppealOutput(BaseModel):
    """
    Complete output of the Grievance & Appeals Agent.
    Includes the drafted letter, regulatory citations, and deadlines.
    """

    # ── Legal Framework ───────────────────────────────────────────
    appeal_framework: AppealFramework = Field(
        ..., description="The legal pathway for this appeal"
    )
    denial_reason: DenialReason = Field(
        ..., description="The classified reason for the claim denial"
    )

    # ── Deadlines ─────────────────────────────────────────────────
    denial_date: date = Field(..., description="Date the denial was issued")
    appeal_deadline: date = Field(..., description="Last date to file the appeal")
    days_remaining: int = Field(..., description="Calendar days remaining to file")

    # ── Appeal Letter ─────────────────────────────────────────────
    appeal_letter: str = Field(
        ..., description="Full drafted letter text (payer appeal OR provider correction)"
    )
    letter_type: str = Field(
        "payer_appeal",
        description=(
            "'payer_appeal': Formal legal appeal to the insurance company (ERISA/ACA/NSA). "
            "'provider_correction': Letter to the hospital billing department requesting "
            "a corrected claim resubmission."
        ),
    )
    letter_format: str = Field(
        "formal", description="Letter format: 'formal', 'urgent_expedited', 'external_review', 'correction_request'"
    )

    # ── Triage Agent Output ───────────────────────────────────────
    triage_path: str = Field(
        "PAYER_ILLEGAL_DENIAL",
        description="'PROVIDER_CODING_ERROR' | 'PAYER_ILLEGAL_DENIAL' — the root cause determination",
    )
    triage_confidence: str = Field(
        "LOW",
        description="'HIGH' | 'MEDIUM' | 'LOW' — Triage Agent's confidence in its decision",
    )
    triage_action_summary: str = Field(
        "",
        description="Patient-facing 1-2 sentence action item from the Triage Agent",
    )
    estimated_success_probability: float = Field(
        0.5,
        description="0.0 to 1.0 — honest estimate of appeal/correction success probability",
    )

    # ── Supporting Evidence ───────────────────────────────────────
    cited_regulations: list[RegulatoryCitation] = Field(
        default_factory=list, description="Specific statutes and precedents cited"
    )
    cited_knowledge_chunks: list[str] = Field(
        default_factory=list, description="concept_ids from RAG knowledge base used in drafting"
    )

    # ── Policy Document Citations (NEW) ───────────────────────────
    policy_citations: list[PolicyCitation] = Field(
        default_factory=list,
        description="Exact clauses from the patient's policy document that contradict the denial, with page numbers"
    )
    contradiction_detected: bool = Field(
        False, description="True if the Policy Analyzer found a direct contradiction in the patient's policy"
    )
    contradiction_strength: str = Field(
        "NONE", description="STRONG | MODERATE | WEAK | NONE"
    )
    appeal_recommendation: str = Field(
        "APPEAL",
        description="STRONG_APPEAL | APPEAL | EXCEPTION_REQUEST | UNLIKELY_TO_WIN | CLAIM_CORRECTLY_DENIED"
    )
    honest_assessment: str = Field(
        "", description="Plain-English honest assessment of the patient's chances"
    )

    # ── Patient-Facing Output ─────────────────────────────────────
    plain_english_summary: str = Field(
        ..., description="Explanation Agent's patient-friendly summary of the appeal and next steps"
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        description="Actionable steps for the patient (e.g., 'Mail this letter via certified mail')"
    )

    # ── Accuracy Core (set by the deterministic appeal_qa node) ───
    # All fields default so previously persisted AppealOutput JSON still validates.
    citation_verification: CitationVerification | None = Field(
        None, description="Deterministic grounding check of every cited statute and quoted policy clause"
    )
    appeal_letter_unannotated: str | None = Field(
        None,
        description="Original letter text, populated only when the verifier inserted [VERIFY] markers or stripped citations",
    )
    success_score: float | None = Field(
        None, ge=0.0, le=1.0,
        description="Deterministic, factor-based success estimate (sits alongside estimated_success_probability)",
    )
    success_score_band: str | None = Field(None, description="'HIGH' | 'MEDIUM' | 'LOW' | 'VERY_LOW'")
    success_score_factors: list[dict] = Field(
        default_factory=list, description="Transparent list of {factor, delta, note} that produced success_score"
    )
    success_score_version: str | None = None
    quality_gate: dict | None = Field(
        None, description="QualityGateResult from the extraction quality gate (missing-information checklist)"
    )
