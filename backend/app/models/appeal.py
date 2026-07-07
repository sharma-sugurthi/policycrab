"""
AppealOutput — structured output of the Grievance & Appeals Agent.
Contains the drafted appeal letter, cited regulations, deadlines,
and a plain-English summary from the Explanation Agent.
"""

from datetime import date
from pydantic import BaseModel, Field
from app.models.enums import AppealFramework, DenialReason


class RegulatoryCitation(BaseModel):
    """A specific regulation or precedent cited in the appeal letter."""
    statute: str = Field(..., description="e.g., 'ERISA 29 CFR §2560.503-1' or 'ACA Section 2704'")
    description: str = Field(..., description="What this statute mandates or prohibits")
    relevance: str = Field(..., description="Why this applies to the patient's specific case")


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
        ..., description="Full drafted appeal letter text"
    )
    letter_format: str = Field(
        "formal", description="Letter format: 'formal', 'urgent_expedited', 'external_review'"
    )

    # ── Supporting Evidence ───────────────────────────────────────
    cited_regulations: list[RegulatoryCitation] = Field(
        default_factory=list, description="Specific statutes and precedents cited"
    )
    cited_knowledge_chunks: list[str] = Field(
        default_factory=list, description="concept_ids from RAG knowledge base used in drafting"
    )

    # ── Patient-Facing Output ─────────────────────────────────────
    plain_english_summary: str = Field(
        ..., description="Explanation Agent's patient-friendly summary of the appeal and next steps"
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        description="Actionable steps for the patient (e.g., 'Mail this letter via certified mail')"
    )
