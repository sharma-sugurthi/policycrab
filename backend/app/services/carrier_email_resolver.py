"""
Carrier Email Resolver Service

Maps insurance carrier names to their known appeals department contacts.
Uses a curated static directory + fuzzy matching.
Falls back to state DOI contact if carrier-specific email is not found.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re

@dataclass
class CarrierEmailProfile:
    carrier_name: str
    appeals_email: Optional[str] = None
    grievances_email: Optional[str] = None
    fax_number: Optional[str] = None
    submission_portal_url: Optional[str] = None
    confidence: str = "HIGH"  # HIGH | MEDIUM | LOW


# ── Curated carrier directory ─────────────────────────────────────────────────
CARRIER_EMAIL_DIRECTORY: dict[str, CarrierEmailProfile] = {
    # Blue Cross Blue Shield variants
    "bcbs": CarrierEmailProfile(
        carrier_name="Blue Cross Blue Shield",
        appeals_email="appeals@bcbs.com",
        grievances_email="grievances@bcbs.com",
        fax_number="1-800-227-7220",
        submission_portal_url="https://www.bcbs.com/member-services",
        confidence="HIGH",
    ),
    "blue cross blue shield": CarrierEmailProfile(
        carrier_name="Blue Cross Blue Shield",
        appeals_email="appeals@bcbs.com",
        grievances_email="grievances@bcbs.com",
        fax_number="1-800-227-7220",
        submission_portal_url="https://www.bcbs.com/member-services",
        confidence="HIGH",
    ),
    "bluecross": CarrierEmailProfile(
        carrier_name="Blue Cross Blue Shield",
        appeals_email="appeals@bcbs.com",
        grievances_email="grievances@bcbs.com",
        fax_number="1-800-227-7220",
        submission_portal_url="https://www.bcbs.com/member-services",
        confidence="HIGH",
    ),
    # Aetna
    "aetna": CarrierEmailProfile(
        carrier_name="Aetna",
        appeals_email="appealscenter@aetna.com",
        grievances_email="memberservices@aetna.com",
        fax_number="1-860-754-2817",
        submission_portal_url="https://member.aetna.com",
        confidence="HIGH",
    ),
    # UnitedHealthcare
    "unitedhealthcare": CarrierEmailProfile(
        carrier_name="UnitedHealthcare",
        appeals_email="appeals@uhc.com",
        grievances_email="grievances@uhc.com",
        fax_number="1-866-748-6027",
        submission_portal_url="https://member.uhc.com",
        confidence="HIGH",
    ),
    "united healthcare": CarrierEmailProfile(
        carrier_name="UnitedHealthcare",
        appeals_email="appeals@uhc.com",
        grievances_email="grievances@uhc.com",
        fax_number="1-866-748-6027",
        submission_portal_url="https://member.uhc.com",
        confidence="HIGH",
    ),
    "uhc": CarrierEmailProfile(
        carrier_name="UnitedHealthcare",
        appeals_email="appeals@uhc.com",
        grievances_email="grievances@uhc.com",
        fax_number="1-866-748-6027",
        submission_portal_url="https://member.uhc.com",
        confidence="HIGH",
    ),
    # Cigna
    "cigna": CarrierEmailProfile(
        carrier_name="Cigna",
        appeals_email="appeals@cigna.com",
        grievances_email="customerservice@cigna.com",
        fax_number="1-800-332-3696",
        submission_portal_url="https://www.cigna.com/individuals-families/member-guide",
        confidence="HIGH",
    ),
    # Humana
    "humana": CarrierEmailProfile(
        carrier_name="Humana",
        appeals_email="appeals@humana.com",
        grievances_email="memberservices@humana.com",
        fax_number="1-800-957-8757",
        submission_portal_url="https://www.humana.com/member",
        confidence="HIGH",
    ),
    # Kaiser Permanente
    "kaiser permanente": CarrierEmailProfile(
        carrier_name="Kaiser Permanente",
        appeals_email="member.appeals@kp.org",
        grievances_email="grievances@kp.org",
        fax_number="1-800-231-9276",
        submission_portal_url="https://healthy.kaiserpermanente.org",
        confidence="HIGH",
    ),
    "kaiser": CarrierEmailProfile(
        carrier_name="Kaiser Permanente",
        appeals_email="member.appeals@kp.org",
        grievances_email="grievances@kp.org",
        fax_number="1-800-231-9276",
        submission_portal_url="https://healthy.kaiserpermanente.org",
        confidence="HIGH",
    ),
    # Anthem
    "anthem": CarrierEmailProfile(
        carrier_name="Anthem",
        appeals_email="appeals@anthem.com",
        grievances_email="memberservices@anthem.com",
        fax_number="1-800-676-2583",
        submission_portal_url="https://www.anthem.com",
        confidence="HIGH",
    ),
    # Molina Healthcare
    "molina": CarrierEmailProfile(
        carrier_name="Molina Healthcare",
        appeals_email="appeals@molinahealthcare.com",
        grievances_email="grievances@molinahealthcare.com",
        fax_number="1-866-449-6849",
        submission_portal_url="https://www.molinahealthcare.com/members",
        confidence="HIGH",
    ),
    "molina healthcare": CarrierEmailProfile(
        carrier_name="Molina Healthcare",
        appeals_email="appeals@molinahealthcare.com",
        grievances_email="grievances@molinahealthcare.com",
        fax_number="1-866-449-6849",
        submission_portal_url="https://www.molinahealthcare.com/members",
        confidence="HIGH",
    ),
    # Centene
    "centene": CarrierEmailProfile(
        carrier_name="Centene",
        appeals_email="appeals@centene.com",
        grievances_email="memberservices@centene.com",
        fax_number="1-866-235-5585",
        submission_portal_url="https://www.centene.com",
        confidence="MEDIUM",
    ),
    # CVS/Aetna
    "cvs health": CarrierEmailProfile(
        carrier_name="CVS Health / Aetna",
        appeals_email="appealscenter@aetna.com",
        grievances_email="memberservices@aetna.com",
        fax_number="1-860-754-2817",
        submission_portal_url="https://www.cvs.com/health",
        confidence="MEDIUM",
    ),
    # WellCare
    "wellcare": CarrierEmailProfile(
        carrier_name="WellCare",
        appeals_email="appeals@wellcare.com",
        grievances_email="grievances@wellcare.com",
        fax_number="1-866-455-4816",
        submission_portal_url="https://www.wellcare.com/member",
        confidence="HIGH",
    ),
    # Oscar Health
    "oscar": CarrierEmailProfile(
        carrier_name="Oscar Health",
        appeals_email="appeals@hioscar.com",
        grievances_email="support@hioscar.com",
        fax_number=None,
        submission_portal_url="https://www.hioscar.com/appeals",
        confidence="HIGH",
    ),
    "oscar health": CarrierEmailProfile(
        carrier_name="Oscar Health",
        appeals_email="appeals@hioscar.com",
        grievances_email="support@hioscar.com",
        fax_number=None,
        submission_portal_url="https://www.hioscar.com/appeals",
        confidence="HIGH",
    ),
    # Bright Health
    "bright health": CarrierEmailProfile(
        carrier_name="Bright Health",
        appeals_email="appeals@brighthealthcare.com",
        grievances_email="memberservices@brighthealthcare.com",
        fax_number="1-855-857-3059",
        submission_portal_url="https://www.brighthealthcare.com/members",
        confidence="MEDIUM",
    ),
    # Friday Health Plans
    "friday health": CarrierEmailProfile(
        carrier_name="Friday Health Plans",
        appeals_email="appeals@fridayhealthplans.com",
        grievances_email="support@fridayhealthplans.com",
        fax_number=None,
        submission_portal_url="https://www.fridayhealthplans.com",
        confidence="MEDIUM",
    ),
    # Highmark
    "highmark": CarrierEmailProfile(
        carrier_name="Highmark",
        appeals_email="appeals@highmarkhealth.org",
        grievances_email="memberservices@highmarkhealth.org",
        fax_number="1-800-544-1987",
        submission_portal_url="https://member.highmarkbcbs.com",
        confidence="HIGH",
    ),
    # Health Net
    "health net": CarrierEmailProfile(
        carrier_name="Health Net",
        appeals_email="appeals@healthnet.com",
        grievances_email="memberservices@healthnet.com",
        fax_number="1-800-628-3199",
        submission_portal_url="https://www.healthnet.com/member",
        confidence="HIGH",
    ),
    # UPMC Health Plan
    "upmc": CarrierEmailProfile(
        carrier_name="UPMC Health Plan",
        appeals_email="appeals@upmchp.com",
        grievances_email="memberservices@upmchp.com",
        fax_number="1-888-876-2756",
        submission_portal_url="https://www.upmchealthplan.com",
        confidence="HIGH",
    ),
    # Geisinger Health Plan
    "geisinger": CarrierEmailProfile(
        carrier_name="Geisinger Health Plan",
        appeals_email="appeals@geisinger.edu",
        grievances_email="memberservices@geisinger.edu",
        fax_number="1-866-379-6828",
        submission_portal_url="https://www.geisinger.org/health-plan",
        confidence="HIGH",
    ),
}

# ── State DOI contacts fallback ───────────────────────────────────────────────
STATE_DOI_CONTACTS: dict[str, dict] = {
    "CA": {"email": "consumer.hotline@insurance.ca.gov", "name": "California Department of Insurance"},
    "TX": {"email": "ConsumerProtection@tdi.texas.gov", "name": "Texas Department of Insurance"},
    "NY": {"email": "consumers@dfs.ny.gov", "name": "New York Department of Financial Services"},
    "FL": {"email": "consumer.helpline@myfloridacfo.com", "name": "Florida Department of Insurance"},
    "IL": {"email": "director@ins.state.il.us", "name": "Illinois Department of Insurance"},
    "PA": {"email": "consumer@insurance.pa.gov", "name": "Pennsylvania Insurance Department"},
    "OH": {"email": "consumer.affairs@insurance.ohio.gov", "name": "Ohio Department of Insurance"},
    "GA": {"email": "commissioner@oci.state.ga.us", "name": "Georgia Department of Insurance"},
    "NC": {"email": "consumer@ncdoi.gov", "name": "North Carolina Department of Insurance"},
    "WA": {"email": "onlineca@oic.wa.gov", "name": "Washington State Office of the Insurance Commissioner"},
    "AZ": {"email": "consumers@azinsurance.gov", "name": "Arizona Department of Insurance"},
    "MA": {"email": "consumer@doi.state.ma.us", "name": "Massachusetts Division of Insurance"},
    "MI": {"email": "DIFS-Complaint@michigan.gov", "name": "Michigan Department of Insurance and Financial Services"},
    "CO": {"email": "DORA_InsuranceConsumer@state.co.us", "name": "Colorado Division of Insurance"},
    "MN": {"email": "consumer.protection@state.mn.us", "name": "Minnesota Department of Commerce"},
    "OR": {"email": "cp.ins@oregon.gov", "name": "Oregon Insurance Division"},
    "VA": {"email": "bureauofinsurance@scc.virginia.gov", "name": "Virginia Bureau of Insurance"},
    "NJ": {"email": "commercial.appeals@dobi.nj.gov", "name": "New Jersey Department of Banking and Insurance"},
}

DEFAULT_DOI = {"email": "contactcms@cms.hhs.gov", "name": "Centers for Medicare & Medicaid Services (CMS)"}


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _fuzzy_match(query: str, directory: dict) -> Optional[str]:
    """Simple token-overlap fuzzy matching against directory keys."""
    query_tokens = set(_normalize(query).split())
    best_key = None
    best_overlap = 0
    for key in directory:
        key_tokens = set(key.split())
        overlap = len(query_tokens & key_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_key = key
    return best_key if best_overlap >= 1 else None


def resolve_carrier_email(carrier_name: str) -> CarrierEmailProfile:
    """
    Resolve the appeal contact for a given carrier name.
    Returns a CarrierEmailProfile with the best available contact info.
    Falls back to a LOW confidence generic profile if no match is found.
    """
    normalized = _normalize(carrier_name)

    # 1. Direct lookup
    if normalized in CARRIER_EMAIL_DIRECTORY:
        return CARRIER_EMAIL_DIRECTORY[normalized]

    # 2. Fuzzy match
    best_key = _fuzzy_match(carrier_name, CARRIER_EMAIL_DIRECTORY)
    if best_key:
        profile = CARRIER_EMAIL_DIRECTORY[best_key]
        return CarrierEmailProfile(
            carrier_name=carrier_name,
            appeals_email=profile.appeals_email,
            grievances_email=profile.grievances_email,
            fax_number=profile.fax_number,
            submission_portal_url=profile.submission_portal_url,
            confidence="MEDIUM",
        )

    # 3. No match — return LOW confidence generic
    return CarrierEmailProfile(
        carrier_name=carrier_name,
        appeals_email=None,
        grievances_email=None,
        fax_number=None,
        submission_portal_url=None,
        confidence="LOW",
    )


def get_state_doi(state: str) -> dict:
    """Returns the State DOI contact for a given 2-letter state code."""
    return STATE_DOI_CONTACTS.get(state.upper(), DEFAULT_DOI)
