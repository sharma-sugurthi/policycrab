"""
State-Specific Regulatory Database — deterministic lookup table.

Maps US state codes to specific appeal deadlines, external review
organizations, surprise billing laws, and Medicaid processes.

Sources:
- State Department of Insurance websites
- NAIC State External Review Survey
- CMS State Balance Billing Protections summary
- KFF State Health Insurance Mandates database

This module is pure logic — no LLM involvement.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StateRegProfile:
    """
    Regulatory profile for a single US state.
    Used to override or supplement the federal framework defaults.
    """
    state_code: str                          # Two-letter USPS state code
    state_name: str

    # ── External Review (ACA § 2719) ──────────────────────────────
    external_review_deadline_days: int       # Days from internal denial to request IRO review
    external_review_org: str                 # Designated IRO or "State DOI" or "Federal FEHB"
    external_review_binding: bool            # Is the IRO decision binding on the insurer?
    external_review_note: str                # State-specific quirk or requirement

    # ── Internal Appeal Deadline ──────────────────────────────────
    internal_appeal_deadline_days: int       # Days from denial to file internal appeal
    internal_appeal_response_days: int       # Days insurer has to respond to internal appeal

    # ── Surprise Billing / Balance Billing ────────────────────────
    state_surprise_billing_law: str | None   # Name of state law, if any (predates or supplements NSA)
    state_surprise_billing_notes: str        # Key patient protections

    # ── Medicaid / CHIP ───────────────────────────────────────────
    medicaid_fair_hearing_days: int          # Days to request Medicaid fair hearing
    medicaid_agency: str                     # State Medicaid agency name

    # ── Additional State Mandates ─────────────────────────────────
    notable_mandates: list[str] = field(default_factory=list)


# ── State Registry ────────────────────────────────────────────────
# Coverage: Top 20 by population + DC. Federal fallback for others.

STATE_REGISTRY: dict[str, StateRegProfile] = {

    "CA": StateRegProfile(
        state_code="CA", state_name="California",
        external_review_deadline_days=180,
        external_review_org="California Dept. of Managed Health Care (DMHC) Independent Medical Review",
        external_review_binding=True,
        external_review_note="CA has TWO separate regulators: DMHC for HMO/MANAGED plans, CDI for indemnity. "
                             "DMHC IMR is highly consumer-friendly and binding within 30 days.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law="AB 72 (2016) — Balance Billing Prohibition",
        state_surprise_billing_notes="CA prohibits balance billing by out-of-network providers at in-network facilities. "
                                     "Predates NSA with broader protections including scheduled procedures.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="CA Department of Health Care Services (DHCS) — Medi-Cal",
        notable_mandates=[
            "Timely access standards: PCP within 10 business days, specialist 15 business days",
            "Mental health parity strictly enforced under CA Mental Health Parity Act",
            "Continuity of care: 12 months with terminated provider for ongoing treatment",
            "No prior auth required for ER care — retrospective review only",
        ],
    ),

    "TX": StateRegProfile(
        state_code="TX", state_name="Texas",
        external_review_deadline_days=60,
        external_review_org="Texas Dept. of Insurance (TDI) — certified IRO",
        external_review_binding=True,
        external_review_note="TX self-funded ERISA plans are preempted from state external review. "
                             "TX has its own surprise billing law for state-regulated plans.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law="HB 1941 (2019) — Texas Surprise Billing Law",
        state_surprise_billing_notes="TX law covers out-of-network emergency care and out-of-network providers at "
                                     "in-network facilities. Patient liability capped at in-network cost-sharing. "
                                     "Predates NSA and provides additional state-level protections.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="TX Health and Human Services Commission — Texas Medicaid",
        notable_mandates=[
            "Annual in-network adequacy filing required from all HMOs",
            "TDI Financial Examination every 3-5 years",
            "Prompt pay: 30 days for electronic clean claims, 45 days for paper",
        ],
    ),

    "FL": StateRegProfile(
        state_code="FL", state_name="Florida",
        external_review_deadline_days=60,
        external_review_org="Florida Dept. of Financial Services (DFS) — contracted IRO",
        external_review_binding=True,
        external_review_note="FL uses a federal external review process for most claims. "
                             "ERISA self-funded plans are exempt from state external review.",
        internal_appeal_deadline_days=365,
        internal_appeal_response_days=45,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="FL relies on federal NSA protections. No independent state surprise billing law. "
                                     "NSA applies for fully insured and ACA plans.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="FL Agency for Health Care Administration (AHCA) — Florida Medicaid",
        notable_mandates=[
            "Florida Managed Care Act: network adequacy oversight by AHCA",
            "Prompt pay: 20 days for electronic, 40 days for paper clean claims",
            "Independent laboratories: anti-steering protections",
        ],
    ),

    "NY": StateRegProfile(
        state_code="NY", state_name="New York",
        external_review_deadline_days=45,
        external_review_org="NY Dept. of Financial Services (DFS) — External Appeal",
        external_review_binding=True,
        external_review_note="NY has one of the most robust external appeal programs. "
                             "Consumer can request external appeal within 45 days of internal denial. "
                             "Expedited external appeal available in 72 hours for urgent situations.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law="NY Surprise Bill Law (2015) — earliest in nation",
        state_surprise_billing_notes="NY law predates NSA and provides independent dispute resolution. "
                                     "Patient pays in-network cost-sharing only for surprise bills. "
                                     "IDR between payer and provider is conducted by the DFS.",
        medicaid_fair_hearing_days=60,
        medicaid_agency="NY Dept. of Health — New York Medicaid (NY Medicaid Choice)",
        notable_mandates=[
            "NY Human Rights Law: broader mental health parity than federal MHPAEA",
            "Network Adequacy Law: travel time standards enforced by DFS",
            "Emergency Services Law: covers 911 responses, air ambulances",
            "Essential Plan (EP): for income 138-200% FPL — unique to NY",
        ],
    ),

    "PA": StateRegProfile(
        state_code="PA", state_name="Pennsylvania",
        external_review_deadline_days=60,
        external_review_org="PA Insurance Department — IRO",
        external_review_binding=True,
        external_review_note="PA uses a state-run IRO system. External review available for "
                             "clinical necessity and experimental treatment denials.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="PA relies on federal NSA. State DOI provides consumer assistance.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="PA Dept. of Human Services — PA Medicaid (Medical Assistance)",
        notable_mandates=[
            "Act 68 (1998): comprehensive managed care consumer protections",
            "Grievance Act: formal grievance and appeal rights for HMO enrollees",
            "Prompt pay: 45 days for electronic, 45 days paper",
        ],
    ),

    "IL": StateRegProfile(
        state_code="IL", state_name="Illinois",
        external_review_deadline_days=60,
        external_review_org="IL Dept. of Insurance (IDOI) — Independent Review Organization",
        external_review_binding=True,
        external_review_note="IL provides independent medical review for coverage disputes. "
                             "No filing fee required. Decision within 30 days.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law="SB 1531 (2019) — IL Balance Billing Act",
        state_surprise_billing_notes="IL prohibits balance billing for emergency services and non-emergency "
                                     "care at in-network facilities. Patient liability capped at in-network amounts.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="IL Dept. of Healthcare and Family Services (HFS) — Illinois Medicaid",
        notable_mandates=[
            "Mental Health and Developmental Disabilities Confidentiality Act",
            "Cancer Screening: mandatory coverage for mammography and colonoscopy",
            "Prompt pay: 30 days electronic, 45 days paper",
        ],
    ),

    "OH": StateRegProfile(
        state_code="OH", state_name="Ohio",
        external_review_deadline_days=60,
        external_review_org="OH Dept. of Insurance (ODI) — IRO",
        external_review_binding=True,
        external_review_note="Ohio external review available for clinical necessity denials. "
                             "Binding on the insurer within 45 days of filing.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="OH relies primarily on federal NSA for surprise billing protections.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="OH Dept. of Medicaid — Ohio Medicaid",
        notable_mandates=[
            "OH HB 386: network adequacy standards for managed Medicaid",
            "Prompt pay: 30 days electronic, 40 days paper",
        ],
    ),

    "GA": StateRegProfile(
        state_code="GA", state_name="Georgia",
        external_review_deadline_days=30,
        external_review_org="GA Dept. of Insurance (OCI) — IRO",
        external_review_binding=True,
        external_review_note="Georgia has a short 30-day window to request external review. "
                             "Act quickly after internal appeal denial.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="GA relies on federal NSA protections. No independent state law.",
        medicaid_fair_hearing_days=30,
        medicaid_agency="GA Dept. of Community Health (DCH) — Georgia Medicaid",
        notable_mandates=[
            "GA Medicaid: strict 30-day fair hearing request window (shorter than most states)",
            "Prompt pay: 15 days electronic, 30 days paper — among fastest in nation",
        ],
    ),

    "NC": StateRegProfile(
        state_code="NC", state_name="North Carolina",
        external_review_deadline_days=60,
        external_review_org="NC Dept. of Insurance (NCDOI) — IRO",
        external_review_binding=True,
        external_review_note="NC offers external review for clinical and contractual denials. "
                             "No filing fee. Decision within 45 days.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="NC relies on federal NSA. NCDOI provides consumer assistance.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="NC Dept. of Health and Human Services (DHHS) — NC Medicaid",
        notable_mandates=[
            "NC Medicaid Transformation: managed care rollout since 2021",
            "Prompt pay: 30 days electronic, 45 days paper",
        ],
    ),

    "MI": StateRegProfile(
        state_code="MI", state_name="Michigan",
        external_review_deadline_days=60,
        external_review_org="MI Dept. of Insurance and Financial Services (DIFS) — IRO",
        external_review_binding=True,
        external_review_note="Michigan offers external review for clinical necessity and experimental "
                             "treatment denials. Decision within 30 days.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="MI relies on federal NSA. DIFS provides consumer complaint intake.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="MI Dept. of Health and Human Services (MDHHS) — Michigan Medicaid",
        notable_mandates=[
            "MI Public Act 350: HMO Act with strong consumer appeal rights",
            "Prompt pay: 45 days electronic and paper",
        ],
    ),

    "NJ": StateRegProfile(
        state_code="NJ", state_name="New Jersey",
        external_review_deadline_days=60,
        external_review_org="NJ Dept. of Banking and Insurance (DOBI) — Independent Utilization Review Organization",
        external_review_binding=True,
        external_review_note="NJ has a comprehensive external review program for all managed care denials. "
                             "Decision binding on insurer within 15-30 days.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=20,
        state_surprise_billing_law="NJ Out-of-Network Consumer Protection Act (2018)",
        state_surprise_billing_notes="NJ law predates NSA. Requires disclosure of OON costs upfront. "
                                     "Patient only pays in-network cost-sharing for surprise OON bills. "
                                     "Arbitration between insurer and provider for disputed amounts.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="NJ Dept. of Human Services (DHS) — NJ FamilyCare / NJ Medicaid",
        notable_mandates=[
            "NJ has strict mental health parity enforcement",
            "Comprehensive Women's Preventive Services mandate",
            "Prompt pay: 30 days electronic, 40 days paper",
        ],
    ),

    "VA": StateRegProfile(
        state_code="VA", state_name="Virginia",
        external_review_deadline_days=60,
        external_review_org="VA Bureau of Insurance (BOI) — URAC-accredited IRO",
        external_review_binding=True,
        external_review_note="Virginia's external review covers clinical necessity and experimental "
                             "treatment. Decision within 15 days for standard, 72 hours for expedited.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law="VA Balance Billing Protection Act (2020)",
        state_surprise_billing_notes="VA law covers emergency services and non-emergency services at "
                                     "in-network facilities. Patient pays in-network cost-sharing only.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="VA Dept. of Medical Assistance Services (DMAS) — Virginia Medicaid",
        notable_mandates=[
            "Prompt pay: 40 days electronic, 40 days paper",
            "FAMIS MOMS: expanded coverage for pregnant women",
        ],
    ),

    "WA": StateRegProfile(
        state_code="WA", state_name="Washington",
        external_review_deadline_days=120,
        external_review_org="WA Office of the Insurance Commissioner (OIC) — Mandated IRO",
        external_review_binding=True,
        external_review_note="WA provides 120 days for external review requests — one of the most "
                             "generous windows. OIC is known for strong consumer advocacy.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=20,
        state_surprise_billing_law="WA SB 5520 (2019) — Balance Billing Protections",
        state_surprise_billing_notes="WA law covers out-of-network emergency and non-emergency services. "
                                     "Providers must provide cost estimates before scheduled care. "
                                     "Patient liability limited to in-network cost-sharing.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="WA Health Care Authority (HCA) — Apple Health (WA Medicaid)",
        notable_mandates=[
            "WA Cares Fund: state long-term care insurance (unique in nation)",
            "Cascade Care: public option plan offered on WA Healthplanfinder",
            "Prompt pay: 20 days electronic, 30 days paper",
        ],
    ),

    "AZ": StateRegProfile(
        state_code="AZ", state_name="Arizona",
        external_review_deadline_days=60,
        external_review_org="AZ Dept. of Insurance and Financial Institutions (DIFI) — IRO",
        external_review_binding=True,
        external_review_note="AZ external review available for clinical necessity denials. "
                             "Decision within 30 days standard, 72 hours expedited.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="AZ relies on federal NSA. DIFI provides consumer complaint intake.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="AZ Health Care Cost Containment System (AHCCCS) — Arizona Medicaid",
        notable_mandates=[
            "AHCCCS is among the most mature Medicaid managed care programs nationally",
            "Prompt pay: 30 days electronic, 45 days paper",
        ],
    ),

    "MA": StateRegProfile(
        state_code="MA", state_name="Massachusetts",
        external_review_deadline_days=30,
        external_review_org="MA Division of Insurance (DOI) — IRO (short window — act fast)",
        external_review_binding=True,
        external_review_note="Massachusetts has a strict 30-day external review request window — "
                             "one of the shortest in the nation. Decision within 10 business days.",
        internal_appeal_deadline_days=30,
        internal_appeal_response_days=30,
        state_surprise_billing_law="MA Acts 2012, Ch. 288 (Chapter 224) — Cost Containment",
        state_surprise_billing_notes="MA law includes surprise billing protections for surprise OON bills. "
                                     "Patients pay in-network cost-sharing at in-network facilities even with OON providers.",
        medicaid_fair_hearing_days=30,
        medicaid_agency="MA Executive Office of Health and Human Services (EOHHS) — MassHealth",
        notable_mandates=[
            "MA Chapter 224: comprehensive health care cost containment with strong patient rights",
            "ConnectorCare: state-subsidized plan for 100-300% FPL on MA Health Connector",
            "Prompt pay: 45 days electronic and paper",
            "MA has mandatory health insurance (state individual mandate)",
        ],
    ),

    "CO": StateRegProfile(
        state_code="CO", state_name="Colorado",
        external_review_deadline_days=60,
        external_review_org="CO Division of Insurance (DOI) — IRO",
        external_review_binding=True,
        external_review_note="CO provides external review for clinical necessity and coverage disputes. "
                             "Decision within 30 days standard, 72 hours expedited.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law="CO SB 20-230 (2020) — Surprise Billing Protections",
        state_surprise_billing_notes="CO law predates NSA for state-regulated plans. "
                                     "Protections for emergency services and facility-based providers. "
                                     "Patient pays in-network cost-sharing only.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="CO Dept. of Health Care Policy and Financing (HCPF) — Health First Colorado",
        notable_mandates=[
            "CO Option: standardized state-sponsored health plan on exchange",
            "CO Mental Health Parity: strong state enforcement",
            "Prompt pay: 30 days electronic, 45 days paper",
        ],
    ),

    "TN": StateRegProfile(
        state_code="TN", state_name="Tennessee",
        external_review_deadline_days=60,
        external_review_org="TN Dept. of Commerce and Insurance (TDCI) — IRO",
        external_review_binding=True,
        external_review_note="TN external review available for clinical necessity denials. "
                             "Binding decision within 45 days.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="TN relies on federal NSA protections.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="TN Bureau of TennCare — TennCare (TN Medicaid)",
        notable_mandates=[
            "TennCare is a managed care-only Medicaid program — one of first in US",
            "Prompt pay: 21 days electronic, 35 days paper",
        ],
    ),

    "MN": StateRegProfile(
        state_code="MN", state_name="Minnesota",
        external_review_deadline_days=60,
        external_review_org="MN Dept. of Commerce (Insurance Division) — IRO",
        external_review_binding=True,
        external_review_note="Minnesota external review covers clinical and contractual denials. "
                             "Decision within 30 days.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="MN relies on federal NSA. Commerce Dept provides consumer assistance.",
        medicaid_fair_hearing_days=30,
        medicaid_agency="MN Dept. of Human Services (DHS) — Medical Assistance (MA)",
        notable_mandates=[
            "MN Comprehensive Health Association (MCHA): high-risk pool history",
            "MinnesotaCare: Basic Health Program for 133-200% FPL",
            "Strong mental health parity enforcement",
            "Prompt pay: 30 days electronic, 45 days paper",
        ],
    ),

    "OR": StateRegProfile(
        state_code="OR", state_name="Oregon",
        external_review_deadline_days=60,
        external_review_org="OR Insurance Division (OID) — IRO",
        external_review_binding=True,
        external_review_note="Oregon provides external review for coverage and clinical necessity disputes. "
                             "Decision within 20 days.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=20,
        state_surprise_billing_law="OR HB 2341 (2017) — Balance Billing Protections",
        state_surprise_billing_notes="OR law predates NSA. Covers OON emergency services and "
                                     "facility-based OON providers. Patient pays in-network rates.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="OR Health Authority (OHA) — Oregon Medicaid (Oregon Health Plan)",
        notable_mandates=[
            "Coordinated Care Organizations (CCOs): unique integrated Medicaid delivery model",
            "Prompt pay: 30 days electronic, 45 days paper",
            "OR Health Plan global budget: cost containment model",
        ],
    ),

    "DC": StateRegProfile(
        state_code="DC", state_name="District of Columbia",
        external_review_deadline_days=60,
        external_review_org="DC Dept. of Insurance, Securities and Banking (DISB) — IRO",
        external_review_binding=True,
        external_review_note="DC external review is binding on the insurer within 30 days. "
                             "DC has strong consumer protections due to small, regulated market.",
        internal_appeal_deadline_days=180,
        internal_appeal_response_days=30,
        state_surprise_billing_law=None,
        state_surprise_billing_notes="DC relies on federal NSA. DISB provides consumer complaint intake.",
        medicaid_fair_hearing_days=90,
        medicaid_agency="DC Dept. of Health Care Finance (DHCF) — DC Medicaid",
        notable_mandates=[
            "DC has individual health insurance mandate",
            "Strong mental health and substance use parity enforcement",
        ],
    ),
}

# ── Federal Fallback ──────────────────────────────────────────────
# Used for states not in the registry above.
FEDERAL_FALLBACK = StateRegProfile(
    state_code="XX",
    state_name="Federal Fallback (State Not in Registry)",
    external_review_deadline_days=120,
    external_review_org="Federal external review process (HHS-designated IRO)",
    external_review_binding=True,
    external_review_note="State not in registry — using conservative federal ACA § 2719 defaults. "
                         "Verify exact deadlines with your state DOI website.",
    internal_appeal_deadline_days=180,
    internal_appeal_response_days=30,
    state_surprise_billing_law=None,
    state_surprise_billing_notes="Federal NSA protections apply for qualifying services.",
    medicaid_fair_hearing_days=90,
    medicaid_agency="State Medicaid agency — check your state's Medicaid website",
    notable_mandates=[
        "Federal ACA § 2719 external review minimum standards apply",
        "ERISA 29 CFR § 2560.503-1 governs self-funded plan appeals",
    ],
)


def get_state_profile(state_code: str) -> StateRegProfile:
    """
    Retrieve the regulatory profile for a given US state.
    Falls back to federal defaults if state not in registry.
    """
    return STATE_REGISTRY.get(state_code.upper().strip(), FEDERAL_FALLBACK)


def get_state_external_review_deadline(state_code: str) -> int:
    """
    Return the external review request deadline in calendar days for a given state.
    Used to override the generic 120-day federal default.
    """
    return get_state_profile(state_code).external_review_deadline_days


def get_state_summary(state_code: str) -> dict:
    """
    Return a JSON-serializable summary of key state regulatory facts.
    Used in appeal letter prompts and API responses.
    """
    p = get_state_profile(state_code)
    return {
        "state_code": p.state_code,
        "state_name": p.state_name,
        "external_review_deadline_days": p.external_review_deadline_days,
        "external_review_org": p.external_review_org,
        "external_review_binding": p.external_review_binding,
        "external_review_note": p.external_review_note,
        "internal_appeal_deadline_days": p.internal_appeal_deadline_days,
        "internal_appeal_response_days": p.internal_appeal_response_days,
        "state_surprise_billing_law": p.state_surprise_billing_law,
        "state_surprise_billing_notes": p.state_surprise_billing_notes,
        "medicaid_fair_hearing_days": p.medicaid_fair_hearing_days,
        "medicaid_agency": p.medicaid_agency,
        "notable_mandates": p.notable_mandates,
        "is_registry_entry": state_code.upper() in STATE_REGISTRY,
    }
