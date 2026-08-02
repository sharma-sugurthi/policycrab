"""
Appeal Studio models — AI Co-Pilot revisions + Evidence Dossier compilation.

The Appeal Studio lets patients inspect their drafted appeal letter line-by-line,
apply one-click AI revisions, and compile everything (letter + EOB highlights +
policy contradictions + regulatory citations) into a single structured dossier
package that the frontend renders as a multi-page PDF.

These models are pure data contracts — all logic lives in
app/services/studio_engine.py and app/api/studio_routes.py.
"""

from datetime import date
from pydantic import BaseModel, Field


# ── AI Co-Pilot Revisions ─────────────────────────────────────────

class RevisionRequest(BaseModel):
    """Payload for a single AI Co-Pilot letter revision."""

    revision_type: str = Field(
        ...,
        description=(
            "One of: 'assertive' | 'state_penalties' | 'simplify_online' | 'medical_urgency'"
        ),
    )
    letter_text: str = Field(
        ...,
        min_length=20,
        description="The current draft appeal letter text to revise.",
    )

    # Context — partial/optional views of the evaluation result.
    policy_profile: dict = Field(default_factory=dict)
    claim_case: dict = Field(default_factory=dict)
    appeal_output: dict = Field(default_factory=dict)
    eob_highlights: dict | None = Field(
        None,
        description="Optional extracted EOB highlights for medical-urgency context.",
    )


class RevisionResponse(BaseModel):
    """Result of a single Co-Pilot revision."""

    success: bool
    revision_type: str
    revised_letter: str | None = Field(
        None,
        description="The revised letter text. Falls back to original text on LLM failure.",
    )
    summary: str = Field(
        "", description="One-sentence summary of what the revision changed."
    )
    focus_changes: list[str] = Field(
        default_factory=list,
        description="Concrete change bullets for the UI diff panel.",
    )
    errors: list[str] = Field(default_factory=list)


# ── Evidence Dossier ──────────────────────────────────────────────

class DossierSection(BaseModel):
    """One named section of the evidence dossier."""

    id: str = Field(..., description="Stable slug: 'letter' | 'eob' | 'policy' | 'regulations' | 'next_steps'")
    title: str = Field(..., description="Human-readable section title")
    body: str | None = Field(None, description="Free-text body (used by the letter section)")
    items: list = Field(
        default_factory=list,
        description="Structured items — dicts for citations, strings for steps/highlights.",
    )


class DossierPackage(BaseModel):
    """
    Normalized, submission-ready dossier package.

    The backend compiles the raw evaluation output into a clean ordered
    structure; the frontend renders this as a professional multi-page PDF.
    """

    success: bool
    generated_at: str = Field(..., description="ISO 8601 timestamp")
    cover: dict = Field(
        ...,
        description="Cover-page metadata: title, plan, carrier, state, framework, deadline.",
    )
    case_summary: str = Field(
        "", description="One-paragraph patient-facing summary for the cover page."
    )
    sections: list[DossierSection] = Field(
        default_factory=list,
        description="Ordered dossier sections (cover already handled separately).",
    )
    totals: dict = Field(
        default_factory=dict,
        description="Compilation stats: word counts, item counts, page estimate.",
    )
    errors: list[str] = Field(default_factory=list)
