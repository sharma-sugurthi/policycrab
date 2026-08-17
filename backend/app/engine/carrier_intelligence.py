"""
Carrier Intelligence — Insurer-specific appeal strategy context.

Maps major US health insurers to their known algorithmic denial systems,
litigation history, reversal rates, and recommended appeal strategies.

This data is injected into the LLM prompt during both triage and grievance
letter drafting, enabling the AI to write more targeted, persuasive appeals
that cite insurer-specific vulnerabilities and legal precedents.

Source data compiled from:
- KB file 05: Algorithmic Claim Denials (nH Predict, PXDX profiles)
- KB file 05: Top US Insurers Denial Profiles
- Congressional hearing records, class-action filings, CMS enforcement actions
"""

from dataclasses import dataclass, field
from app.engine.carrier_directory import find_carrier


@dataclass(frozen=True)
class CarrierIntelligence:
    """Insurer-specific intelligence for targeted appeal strategy."""
    carrier_id: str
    display_name: str

    # Algorithmic denial systems
    algorithmic_system: str | None = None
    algorithmic_system_description: str | None = None

    # Known denial pattern statistics
    denial_rate_context: str | None = None
    reversal_rate_on_appeal: str | None = None

    # Litigation and regulatory exposure
    litigation_context: list[str] = field(default_factory=list)

    # CMS/regulatory actions
    regulatory_actions: list[str] = field(default_factory=list)

    # Specific appeal strategy guidance for the LLM
    appeal_strategy_notes: list[str] = field(default_factory=list)

    # Specific post-acute / service categories with elevated denial rates
    high_risk_denial_categories: list[str] = field(default_factory=list)


# ── Carrier Intelligence Database ─────────────────────────────────
# Each entry maps an insurer to its known denial patterns, litigation
# exposure, and actionable strategy notes for the LLM.

CARRIER_INTELLIGENCE: dict[str, CarrierIntelligence] = {
    "unitedhealthcare": CarrierIntelligence(
        carrier_id="unitedhealthcare",
        display_name="UnitedHealthcare (UHC)",
        algorithmic_system="nH Predict (naviHealth)",
        algorithmic_system_description=(
            "UnitedHealthcare's nH Predict algorithm (developed by subsidiary naviHealth) "
            "predicts patient recovery trajectories for Medicare Advantage post-acute care. "
            "Class-action lawsuits allege UHC used nH Predict to rigidly terminate coverage "
            "based on statistical population averages rather than individualized clinical judgment."
        ),
        denial_rate_context=(
            "Post-acute care denial rate increased from 10.9% in 2020 to 22.7% in 2022 "
            "after nH Predict deployment."
        ),
        reversal_rate_on_appeal="~90% reversal rate when nH Predict denials are formally appealed",
        litigation_context=[
            "Estate of Lokken v. UnitedHealth Group (class action) — alleges nH Predict denied coverage "
            "based on algorithm rather than individual patient needs",
            "Senate Finance Committee investigation (2023) into UHC's use of AI in Medicare Advantage coverage decisions",
        ],
        regulatory_actions=[
            "CMS issued guidance in 2024 requiring Medicare Advantage plans to ensure AI-assisted "
            "coverage determinations are based on individual patient circumstances, not solely algorithmic predictions",
        ],
        appeal_strategy_notes=[
            "Explicitly state that the denial appears to be based on a predictive algorithm (nH Predict) "
            "rather than individualized clinical review of the patient's specific medical records",
            "Cite CMS 2024 guidance requiring individualized review for MA coverage determinations",
            "Note the ~90% reversal rate when nH Predict denials are formally appealed — this demonstrates "
            "the algorithm's unreliability as a basis for coverage decisions",
            "Request disclosure of whether the denial was generated or informed by an AI/algorithmic system, "
            "as required by multiple state AI transparency laws (e.g., California SB 1120)",
        ],
        high_risk_denial_categories=[
            "Post-acute care (skilled nursing facility stays)",
            "Home health services",
            "Inpatient rehabilitation",
            "Physical therapy continuation",
        ],
    ),

    "cigna": CarrierIntelligence(
        carrier_id="cigna",
        display_name="Cigna / The Cigna Group",
        algorithmic_system="PXDX (Procedure-Diagnosis)",
        algorithmic_system_description=(
            "Cigna's PXDX system enables medical directors to deny batches of claims based on "
            "procedure code and diagnosis code combinations, with an alleged average review time "
            "of approximately 1.2 seconds per claim — a velocity that renders genuine individualized "
            "clinical review physically impossible."
        ),
        denial_rate_context=(
            "PXDX system reportedly facilitated the denial of over 300,000 claims in a two-month period."
        ),
        reversal_rate_on_appeal="High reversal rate on appeal — algorithmic batch denials rarely survive individual scrutiny",
        litigation_context=[
            "Class-action lawsuit alleging PXDX denied claims without medical directors opening individual patient files",
            "ProPublica investigation documented the 1.2-second average review time",
        ],
        regulatory_actions=[],
        appeal_strategy_notes=[
            "Argue that the denial could not have been based on individualized clinical review given "
            "Cigna's documented PXDX batch-processing system with 1.2-second average review times",
            "Demand disclosure of whether the denying medical director reviewed the patient's specific "
            "medical records before issuing the denial, as required by ERISA's 'full and fair review' mandate",
            "Cite ERISA 29 CFR § 2560.503-1(h)(3)(iv) — the reviewing physician must consider "
            "the claimant's specific medical circumstances",
            "Reference the ProPublica investigation and class-action filings as evidence of Cigna's "
            "pattern of algorithmic batch denials",
        ],
        high_risk_denial_categories=[
            "Claims with common procedure-diagnosis combinations",
            "Lab tests and diagnostic procedures",
            "Outpatient mental health services",
        ],
    ),

    "humana": CarrierIntelligence(
        carrier_id="humana",
        display_name="Humana",
        algorithmic_system=None,
        algorithmic_system_description=None,
        denial_rate_context=(
            "Senate investigations revealed Humana denies skilled nursing and rehabilitation "
            "claims at rates significantly higher than traditional (Original) Medicare."
        ),
        reversal_rate_on_appeal=None,
        litigation_context=[
            "Senate Finance Committee investigation into MA denial rates for post-acute care",
        ],
        regulatory_actions=[
            "CMS 2024 guidance on individualized coverage determinations applies to Humana MA plans",
        ],
        appeal_strategy_notes=[
            "Compare the denial to Original Medicare coverage criteria — if Original Medicare would "
            "cover the service, the MA plan must provide equivalent coverage per CMS regulations",
            "Cite CMS requirement that MA plans cannot impose utilization management restrictions "
            "more burdensome than Original Medicare for the same service category",
            "For Medicare Advantage post-acute denials, reference the Senate investigation findings",
        ],
        high_risk_denial_categories=[
            "Skilled nursing facility stays",
            "Inpatient rehabilitation",
            "Home health continuation",
        ],
    ),

    "aetna": CarrierIntelligence(
        carrier_id="aetna",
        display_name="Aetna (CVS Health)",
        algorithmic_system=None,
        algorithmic_system_description=None,
        denial_rate_context=(
            "Aetna employs stringent prior authorization protocols and algorithmic reviews "
            "for inpatient claims. Maintains a highly defensive posture against post-acute care expenditures."
        ),
        reversal_rate_on_appeal=None,
        litigation_context=[
            "Former Aetna medical director testified in deposition (Orrana v. Aetna, 2018) that he "
            "approved or denied claims without reviewing patient medical records",
        ],
        regulatory_actions=[],
        appeal_strategy_notes=[
            "Aetna often requires their specific Member Complaint and Appeal Form — ensure it is attached",
            "For prior authorization denials, request peer-to-peer review between the treating physician "
            "and Aetna's medical director before filing the written appeal",
            "Cite the Orrana v. Aetna deposition testimony if the denial appears to lack individualized review",
        ],
        high_risk_denial_categories=[
            "Inpatient admissions",
            "Prior authorization-dependent procedures",
            "Post-acute care",
        ],
    ),

    "anthem": CarrierIntelligence(
        carrier_id="anthem",
        display_name="Anthem / Elevance Health (BCBS)",
        algorithmic_system=None,
        algorithmic_system_description=None,
        denial_rate_context=(
            "Anthem/Elevance utilizes vast historical claims data to enforce strict medical necessity "
            "criteria, often requiring extensive peer-to-peer reviews during the grievance process."
        ),
        reversal_rate_on_appeal=None,
        litigation_context=[],
        regulatory_actions=[],
        appeal_strategy_notes=[
            "Anthem typically requires extensive clinical documentation — include all medical records, "
            "lab results, and the treating physician's letter of medical necessity",
            "Be prepared for a peer-to-peer review request — the appeal letter should anticipate "
            "and preemptively address Anthem's likely objections based on their published clinical policies",
            "Ensure the Member ID prefix is included on all correspondence",
        ],
        high_risk_denial_categories=[
            "Medical necessity determinations",
            "Advanced imaging (MRI, CT)",
        ],
    ),

    "centene": CarrierIntelligence(
        carrier_id="centene",
        display_name="Centene (Ambetter / Wellcare)",
        algorithmic_system=None,
        algorithmic_system_description=None,
        denial_rate_context=(
            "Centene operates in heavily regulated government-program environments (Medicaid, "
            "ACA marketplace via Ambetter), resulting in historically high administrative denial rates "
            "driven by strict state-specific Medicaid contracting rules and eligibility verification."
        ),
        reversal_rate_on_appeal=None,
        litigation_context=[],
        regulatory_actions=[],
        appeal_strategy_notes=[
            "For Ambetter marketplace plans, cite ACA Section 2719 and 45 CFR § 147.136 for appeal rights",
            "For Medicaid managed care (Wellcare), request a state fair hearing if the internal MCO appeal is denied",
            "Addresses vary heavily by state — verify the appeal address on the back of the Member ID card",
        ],
        high_risk_denial_categories=[
            "Eligibility verification denials",
            "Prior authorization requirements",
            "Step therapy enforcement",
        ],
    ),

    "molina": CarrierIntelligence(
        carrier_id="molina",
        display_name="Molina Healthcare",
        algorithmic_system=None,
        algorithmic_system_description=None,
        denial_rate_context=(
            "Molina exhibits some of the highest ACA marketplace denial rates (~22%), "
            "driven by strict step-therapy requirements and prior authorization demands."
        ),
        reversal_rate_on_appeal=None,
        litigation_context=[],
        regulatory_actions=[],
        appeal_strategy_notes=[
            "For step therapy denials, provide clinical documentation showing the patient has tried "
            "and failed on the required lower-tier medications",
            "For Medicaid plans, state fair hearing requests must be sent to the State Medicaid Agency, not just Molina",
            "The ~22% denial rate on marketplace plans means persistence with appeals is especially important",
        ],
        high_risk_denial_categories=[
            "Step therapy enforcement",
            "Prior authorization for specialty drugs",
            "ACA marketplace claim denials",
        ],
    ),

    "kaiser": CarrierIntelligence(
        carrier_id="kaiser",
        display_name="Kaiser Permanente",
        algorithmic_system=None,
        algorithmic_system_description=None,
        denial_rate_context=(
            "Kaiser operates as both insurer and care provider within a closed Integrated Delivery "
            "Network (IDN). This alignment results in an exceptionally low ACA marketplace denial rate (~6%)."
        ),
        reversal_rate_on_appeal=None,
        litigation_context=[],
        regulatory_actions=[],
        appeal_strategy_notes=[
            "Because Kaiser is the insurer AND provider, appeals should focus strictly on clinical "
            "guidelines and Kaiser's Evidence of Coverage (EOC) document",
            "The low 6% denial rate means Kaiser denials may be more clinically justified than average — "
            "ensure strong clinical evidence supports the appeal",
            "In California, Kaiser is regulated by DMHC under Knox-Keene — the Independent Medical "
            "Review (IMR) process through DMHC is binding on Kaiser and historically favors patients",
        ],
        high_risk_denial_categories=[
            "Out-of-network referrals (rare by design)",
            "Experimental/investigational treatments",
        ],
    ),
}


def get_carrier_intelligence(carrier_name: str) -> CarrierIntelligence | None:
    """
    Look up insurer-specific intelligence by carrier name.

    Uses multiple matching strategies:
    1. Carrier directory fuzzy matching (handles aliases like "UHC", "Anthem BCBS")
    2. Direct key lookup in CARRIER_INTELLIGENCE (handles exact IDs)
    3. Normalized substring matching (handles "UnitedHealthcare" → "unitedhealthcare")
    """
    if not carrier_name:
        return None

    # Strategy 1: Use the carrier directory fuzzy matcher
    carrier_profile = find_carrier(carrier_name)
    if carrier_profile and carrier_profile.id in CARRIER_INTELLIGENCE:
        return CARRIER_INTELLIGENCE[carrier_profile.id]

    # Strategy 2: Direct key lookup with normalized input
    import re
    normalized = re.sub(r'[^a-z0-9]', '', carrier_name.lower())
    for key, intel in CARRIER_INTELLIGENCE.items():
        normalized_key = re.sub(r'[^a-z0-9]', '', key)
        if normalized == normalized_key or normalized_key in normalized or normalized in normalized_key:
            return intel

    return None


def format_carrier_intelligence_for_prompt(intel: CarrierIntelligence) -> str:
    """
    Format carrier intelligence into a structured text block
    suitable for injection into an LLM prompt.
    """
    lines = [
        f"\nINSURER-SPECIFIC INTELLIGENCE ({intel.display_name}):",
    ]

    if intel.algorithmic_system:
        lines.append(f"⚠️  ALGORITHMIC DENIAL SYSTEM DETECTED: {intel.algorithmic_system}")
        lines.append(f"   {intel.algorithmic_system_description}")

    if intel.denial_rate_context:
        lines.append(f"📊 DENIAL PATTERN: {intel.denial_rate_context}")

    if intel.reversal_rate_on_appeal:
        lines.append(f"📈 REVERSAL RATE: {intel.reversal_rate_on_appeal}")

    if intel.litigation_context:
        lines.append("⚖️  LITIGATION CONTEXT:")
        for item in intel.litigation_context:
            lines.append(f"   • {item}")

    if intel.regulatory_actions:
        lines.append("🏛️  REGULATORY ACTIONS:")
        for item in intel.regulatory_actions:
            lines.append(f"   • {item}")

    if intel.appeal_strategy_notes:
        lines.append("🎯 APPEAL STRATEGY GUIDANCE (use these in the letter):")
        for note in intel.appeal_strategy_notes:
            lines.append(f"   • {note}")

    if intel.high_risk_denial_categories:
        lines.append("🔴 HIGH-RISK DENIAL CATEGORIES for this insurer:")
        for cat in intel.high_risk_denial_categories:
            lines.append(f"   • {cat}")

    return "\n".join(lines)

