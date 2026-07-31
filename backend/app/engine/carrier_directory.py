"""
Carrier Contact Directory — Static data module for major US health insurers.

Provides submission addresses, fax numbers, and portal URLs for the top 10 US payers.
Includes fuzzy matching logic to link a PolicyProfile's `carrier_name` to a known profile.
"""

from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class CarrierProfile:
    id: str
    display_name: str
    aliases: list[str]
    
    appeal_mailing_address: str
    appeal_fax_number: str | None
    appeal_email: str | None
    appeal_portal_url: str | None
    
    member_services_phone: str | None
    appeals_department_phone: str | None
    
    special_notes: str | None
    last_verified: str


CARRIER_DIRECTORY = {
    "unitedhealthcare": CarrierProfile(
        id="unitedhealthcare",
        display_name="UnitedHealthcare (UHC)",
        aliases=["uhc", "united health", "united healthcare", "unitedhealth group", "oxford", "golden rule", "umr"],
        appeal_mailing_address="UnitedHealthcare - Appeals & Grievances\nP.O. Box 30432\nSalt Lake City, UT 84130-0432",
        appeal_fax_number="1-801-994-1082",
        appeal_email=None,
        appeal_portal_url="https://myuhc.com",
        member_services_phone="1-866-414-1959",
        appeals_department_phone=None,
        special_notes="UHC highly prefers appeals submitted via the MyUHC member portal. For self-funded ERISA plans (UMR), check the back of your ID card as the address may differ.",
        last_verified="2026-07-30"
    ),
    
    "anthem": CarrierProfile(
        id="anthem",
        display_name="Anthem / Elevance Health (BCBS)",
        aliases=["anthem", "elevance", "empire bcbs", "anthem blue cross", "anthem bcbs"],
        appeal_mailing_address="Anthem Blue Cross - Appeals Department\nP.O. Box 105568\nAtlanta, GA 30348-5568",
        appeal_fax_number="1-888-859-3046",
        appeal_email=None,
        appeal_portal_url="https://www.anthem.com/login/",
        member_services_phone="1-800-331-1476",
        appeals_department_phone=None,
        special_notes="Anthem operates BCBS in 14 states. Ensure you include the prefix from your Member ID on all correspondence.",
        last_verified="2026-07-30"
    ),
    
    "aetna": CarrierProfile(
        id="aetna",
        display_name="Aetna (CVS Health)",
        aliases=["aetna", "cvs health", "aetna life"],
        appeal_mailing_address="Aetna - Member Appeals\nP.O. Box 14463\nLexington, KY 40512",
        appeal_fax_number="1-859-425-3379",
        appeal_email=None,
        appeal_portal_url="https://www.aetna.com/secure-login.html",
        member_services_phone="1-800-US-AETNA",
        appeals_department_phone=None,
        special_notes="Aetna often requires their specific Member Complaint and Appeal Form to be attached to your letter.",
        last_verified="2026-07-30"
    ),
    
    "cigna": CarrierProfile(
        id="cigna",
        display_name="Cigna / The Cigna Group",
        aliases=["cigna", "the cigna group", "evernorth"],
        appeal_mailing_address="Cigna - Member Appeals\nP.O. Box 188011\nChattanooga, TN 37422",
        appeal_fax_number="1-877-815-4827",
        appeal_email=None,
        appeal_portal_url="https://my.cigna.com",
        member_services_phone="1-800-244-6224",
        appeals_department_phone=None,
        special_notes="Cigna appeals must clearly state 'Appeal' at the top of the letter to avoid being routed as general correspondence.",
        last_verified="2026-07-30"
    ),
    
    "humana": CarrierProfile(
        id="humana",
        display_name="Humana",
        aliases=["humana", "humana insurance"],
        appeal_mailing_address="Humana - Grievances and Appeals\nP.O. Box 14165\nLexington, KY 40512-4165",
        appeal_fax_number="1-800-949-2961",
        appeal_email=None,
        appeal_portal_url="https://www.humana.com/log-in",
        member_services_phone="1-800-448-6262",
        appeals_department_phone=None,
        special_notes="For Humana Medicare Advantage plans, use the expedited appeals fax line (1-800-595-0462) for clinically urgent denials.",
        last_verified="2026-07-30"
    ),
    
    "kaiser": CarrierProfile(
        id="kaiser",
        display_name="Kaiser Permanente",
        aliases=["kaiser", "kaiser permanente", "kp"],
        appeal_mailing_address="Kaiser Permanente - Member Appeals\nAttn: Member Appeals\nP.O. Box 1281\nSan Leandro, CA 94577",
        appeal_fax_number=None,
        appeal_email=None,
        appeal_portal_url="https://kp.org",
        member_services_phone="1-800-464-4000",
        appeals_department_phone=None,
        special_notes="Kaiser is an HMO where the insurer and provider are the same entity. Appeals should focus strictly on clinical guidelines and Kaiser's Evidence of Coverage (EOC).",
        last_verified="2026-07-30"
    ),
    
    "centene": CarrierProfile(
        id="centene",
        display_name="Centene (Ambetter / Wellcare)",
        aliases=["centene", "ambetter", "wellcare", "fidelis"],
        appeal_mailing_address="Ambetter - Appeals and Grievances\nP.O. Box 10341\nVan Nuys, CA 91410",
        appeal_fax_number="1-877-941-8079",
        appeal_email=None,
        appeal_portal_url="https://ambetter.centene.com/",
        member_services_phone="1-877-687-1196",
        appeals_department_phone=None,
        special_notes="Addresses vary heavily by state for Ambetter plans. Verify the address on the back of your Member ID card.",
        last_verified="2026-07-30"
    ),
    
    "molina": CarrierProfile(
        id="molina",
        display_name="Molina Healthcare",
        aliases=["molina", "molina healthcare"],
        appeal_mailing_address="Molina Healthcare - Appeals & Grievances\nP.O. Box 22816\nLong Beach, CA 90801",
        appeal_fax_number="1-562-499-0610",
        appeal_email=None,
        appeal_portal_url="https://mycaresource.com",
        member_services_phone="1-888-562-5442",
        appeals_department_phone=None,
        special_notes="For Molina Medicaid plans, state fair hearing requests must often be sent to the State Medicaid Agency, not just Molina.",
        last_verified="2026-07-30"
    ),
    
    "hcsc": CarrierProfile(
        id="hcsc",
        display_name="HCSC (BCBS IL/TX/MT/OK/NM)",
        aliases=["hcsc", "health care service corp", "bcbs il", "bcbs tx", "bcbs ok", "bcbs nm", "bcbs mt", "blue cross blue shield illinois", "blue cross blue shield texas"],
        appeal_mailing_address="HCSC - Member Appeals\nP.O. Box 3283\nNaperville, IL 60566-7283",
        appeal_fax_number="1-888-282-0545",
        appeal_email=None,
        appeal_portal_url="https://www.bcbsil.com/member",
        member_services_phone="1-800-538-8833",
        appeals_department_phone=None,
        special_notes="HCSC operates BCBS in 5 states. Appeals must include the completed generic BCBS Member Appeal Form.",
        last_verified="2026-07-30"
    ),
    
    "highmark": CarrierProfile(
        id="highmark",
        display_name="Highmark (BCBS PA/WV/DE/NY)",
        aliases=["highmark", "highmark bcbs", "bcbs pa", "bcbs wv", "bcbs de"],
        appeal_mailing_address="Highmark - Member Appeals Department\nP.O. Box 535095\nPittsburgh, PA 15253-5095",
        appeal_fax_number="1-866-333-6592",
        appeal_email=None,
        appeal_portal_url="https://www.highmarkbcbs.com",
        member_services_phone="1-800-241-5704",
        appeals_department_phone=None,
        special_notes="Highmark typically requires a completed 'Member Appeal Request Form' to accompany any narrative appeal letter.",
        last_verified="2026-07-30"
    )
}


def normalize_string(s: str) -> str:
    """Lowercases, removes punctuation, and standardizes spacing."""
    s = s.lower()
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def find_carrier(carrier_name: str) -> CarrierProfile | None:
    """
    Fuzzy match a user's carrier name to the directory.
    Checks exact matches, then alias matches, then substring matches.
    """
    if not carrier_name:
        return None
        
    normalized_input = normalize_string(carrier_name)
    
    # 1. Exact match on aliases
    for profile in CARRIER_DIRECTORY.values():
        if normalized_input in profile.aliases or normalized_input == normalize_string(profile.display_name):
            return profile
            
    # 2. Substring match
    for profile in CARRIER_DIRECTORY.values():
        for alias in profile.aliases:
            if alias in normalized_input or normalized_input in alias:
                return profile
                
    return None
