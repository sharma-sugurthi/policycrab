"""
Citation Allowlist — the set of statutes, regulations and guidance documents that
PolicyCrab's appeal letters are permitted to cite as VERIFIED.

Why this exists
---------------
The LLM that drafts appeal letters is told "never fabricate citations", but an
instruction is not a guarantee. This module is the deterministic ground truth the
citation verifier (app/engine/citation_verifier.py) checks against. Anything the
letter cites that is not here — and not literally present in a knowledge-base
chunk retrieved for the case — is marked [VERIFY] in the letter.

Sourcing discipline
-------------------
Every entry carries:
  source_url    — the authoritative page for the provision (eCFR for CFR sections,
                  uscode.house.gov for U.S.C. sections, dol.gov for DOL guidance).
                  URLs follow each publisher's canonical addressing scheme.
  verified_on   — ISO date on which a human opened source_url and confirmed the
                  provision exists and says what `display`/`aliases` claim.
                  None means NOT YET HUMAN-VERIFIED.
  needs_human_verification — True until verified_on is set.

The build environment this module was authored in could not reach ecfr.gov or
uscode.house.gov, so every entry ships with verified_on=None. The verifier
surfaces this as the flag ALLOWLIST_NEEDS_HUMAN_VERIFICATION until a maintainer
runs `python scripts/build_citation_allowlist.py --checklist`, opens each URL,
and fills in verified_on. tests/test_citation_allowlist_sync.py enforces that
every entry has either a verified_on date or needs_human_verification=True —
silent, unsourced entries cannot be added.

Case law (e.g. Estate of Lokken v. UnitedHealth Group) is deliberately NOT in
this list: no primary-source URL could be confirmed from this environment, so
the verifier will flag case names for human review. Add them here with a court
docket URL once confirmed.

Keys are canonical strings produced by citation_verifier.normalize_statute():
  "29 CFR § 2560.503-1" -> "29cfr2560.503-1"
  "29 U.S.C. § 1132"    -> "29usc1132"
  "ACA Section 2719"    -> "phsa2719"   (ACA §§27xx are PHSA §§27xx)
  "DOL Technical Release 2010-01" -> "doltr2010-01"
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AllowedCitation:
    canonical: str
    display: str
    source_url: str
    origin: str                                  # where in the codebase this is asserted
    aliases: tuple[str, ...] = ()
    kb_concept_ids: tuple[str, ...] = ()
    verified_on: str | None = None               # ISO date; None = not yet human-verified
    needs_human_verification: bool = True
    note: str = ""


def _ecfr_section(title: int, section: str) -> str:
    return f"https://www.ecfr.gov/current/title-{title}/section-{section}"


def _ecfr_part(title: int, part: str) -> str:
    return f"https://www.ecfr.gov/current/title-{title}/part-{part}"


def _usc(title: int, section: str) -> str:
    return (
        "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title"
        f"{title}-section{section}&num=0&edition=prelim"
    )


_ENTRIES: list[AllowedCitation] = [
    # ── ERISA claims procedure & enforcement ──────────────────────
    AllowedCitation(
        canonical="29cfr2560.503-1",
        display="29 CFR § 2560.503-1",
        source_url=_ecfr_section(29, "2560.503-1"),
        origin="regulatory_router;grievance.CARC_PRECEDENTS;deadline_calculator;carrier_intelligence",
        aliases=("erisa503", "erisa section 503", "erisa sec. 503", "erisa 503",
                 "erisa claims procedure regulation"),
        note="Claims procedure — full and fair review, 180-day appeal window, disclosure of rules/guidelines.",
    ),
    AllowedCitation(
        canonical="29usc1132",
        display="29 U.S.C. § 1132",
        source_url=_usc(29, "1132"),
        origin="regulatory_router;knowledge_base/02",
        aliases=("erisa502", "erisa section 502", "erisa 502(a)", "erisa section 502(a)", "erisa502(a)"),
        note="ERISA § 502 civil enforcement.",
    ),
    AllowedCitation(
        canonical="29usc1133",
        display="29 U.S.C. § 1133",
        source_url=_usc(29, "1133"),
        origin="grievance.CARC_PRECEDENTS (statutory basis of ERISA § 503)",
        aliases=(),
        note="ERISA § 503 claims procedure (statute); regulation is 29 CFR 2560.503-1.",
    ),
    AllowedCitation(
        canonical="29usc1144",
        display="29 U.S.C. § 1144",
        source_url=_usc(29, "1144"),
        origin="knowledge_base/02;state_profiles",
        aliases=("erisa514", "erisa section 514", "erisa 514(a)", "erisa section 514(a)",
                 "erisa514(a)", "erisa514(b)(2)", "erisa section 514(b)(2)"),
        note="ERISA § 514 preemption / savings clause.",
    ),
    AllowedCitation(
        canonical="29usc1185a",
        display="29 U.S.C. § 1185a",
        source_url=_usc(29, "1185a"),
        origin="grievance prompt rule 12 (MHPAEA)",
        aliases=("mhpaea", "mental health parity and addiction equity act", "erisa712", "erisa section 712"),
        note="Mental Health Parity and Addiction Equity Act (ERISA § 712).",
    ),
    AllowedCitation(
        canonical="doltr2010-01",
        display="DOL Technical Release 2010-01",
        source_url="https://www.dol.gov/agencies/ebsa/employers-and-advisers/guidance/technical-releases/10-01",
        origin="appeal_routes.LEVEL_CONFIGS",
        aliases=("technical release 2010-01",),
        note="Interim federal external review process guidance.",
    ),

    # ── ACA / PHSA appeal & coverage rights ───────────────────────
    AllowedCitation(
        canonical="45cfr147.136",
        display="45 CFR § 147.136",
        source_url=_ecfr_section(45, "147.136"),
        origin="regulatory_router;grievance prompt rule 14;appeal_routes.LEVEL_CONFIGS",
        aliases=(),
        note="Internal claims and appeals and external review processes.",
    ),
    AllowedCitation(
        canonical="phsa2719",
        display="PHSA § 2719 (ACA § 2719)",
        source_url=_usc(42, "300gg-19"),
        origin="regulatory_router;appeal_routes;grievance.CARC_PRECEDENTS;state_profiles",
        aliases=("aca section 2719", "aca § 2719", "42usc300gg-19", "section 2719 of the public health service act"),
        note="Appeals process — codified at 42 U.S.C. § 300gg-19.",
    ),
    AllowedCitation(
        canonical="phsa2704",
        display="PHSA § 2704 (ACA § 2704)",
        source_url=_usc(42, "300gg-3"),
        origin="models/appeal;enums.DenialReason.PRE_EXISTING_CONDITION",
        aliases=("aca section 2704", "42usc300gg-3"),
        note="Prohibition of preexisting condition exclusions — 42 U.S.C. § 300gg-3.",
    ),
    AllowedCitation(
        canonical="phsa2701",
        display="PHSA § 2701 (ACA § 2701)",
        source_url=_usc(42, "300gg"),
        origin="knowledge_base/05",
        aliases=("aca section 2701", "42usc300gg"),
        note="Fair health insurance premiums — 42 U.S.C. § 300gg.",
    ),
    AllowedCitation(
        canonical="phsa2718",
        display="PHSA § 2718 (ACA § 2718)",
        source_url=_usc(42, "300gg-18"),
        origin="knowledge_base/02",
        aliases=("aca section 2718", "42usc300gg-18"),
        note="Medical loss ratio — 42 U.S.C. § 300gg-18.",
    ),
    AllowedCitation(
        canonical="phsa1302",
        display="ACA § 1302",
        source_url=_usc(42, "18022"),
        origin="knowledge_base/02",
        aliases=("aca section 1302", "aca section 1302(b)", "aca 1302(b)", "42usc18022", "essential health benefits statute"),
        note="Essential health benefits — 42 U.S.C. § 18022 (ACA's own section, not PHSA).",
    ),
    AllowedCitation(
        canonical="45cfr156.110",
        display="45 CFR § 156.110",
        source_url=_ecfr_section(45, "156.110"),
        origin="grievance prompt rule 14",
        note="EHB-benchmark plan standards.",
    ),
    AllowedCitation(
        canonical="45cfr156.122",
        display="45 CFR § 156.122",
        source_url=_ecfr_section(45, "156.122"),
        origin="regulatory_router;grievance prompt rule 13",
        aliases=("45cfr156.122(c)",),
        note="Prescription drug benefits — formulary exception process in paragraph (c).",
    ),
    AllowedCitation(
        canonical="45cfr156.115",
        display="45 CFR § 156.115",
        source_url=_ecfr_section(45, "156.115"),
        origin="knowledge_base/02 (EHB provision)",
        note="Provision of EHB.",
    ),

    # ── No Surprises Act ──────────────────────────────────────────
    AllowedCitation(
        canonical="45cfr149",
        display="45 CFR Part 149",
        source_url=_ecfr_part(45, "149"),
        origin="regulatory_router (NSA_IDR)",
        aliases=("no surprises act", "nsa"),
        note="Surprise billing and transparency requirements.",
    ),
    AllowedCitation(
        canonical="45cfr149.410",
        display="45 CFR § 149.410",
        source_url=_ecfr_section(45, "149.410"),
        origin="triage (NSA ancillary rule);models/claim",
        aliases=("45cfr149.410(b)",),
        note="Balance billing for non-emergency services by nonparticipating providers at participating facilities.",
    ),
    AllowedCitation(
        canonical="45cfr149.110",
        display="45 CFR § 149.110",
        source_url=_ecfr_section(45, "149.110"),
        origin="cost_calculator (NSA emergency scenario)",
        note="Preventing surprise medical bills for emergency services.",
    ),
    AllowedCitation(
        canonical="45cfr149.120",
        display="45 CFR § 149.120",
        source_url=_ecfr_section(45, "149.120"),
        origin="cost_calculator (NSA non-emergency at INN facility)",
        note="Preventing surprise medical bills for non-emergency services at participating facilities.",
    ),
    AllowedCitation(
        canonical="42usc300gg-111",
        display="42 U.S.C. § 300gg-111",
        source_url=_usc(42, "300gg-111"),
        origin="knowledge_base/02 (NSA statute)",
        aliases=("phsa2799a-1",),
        note="NSA — preventing surprise medical bills (PHSA § 2799A-1).",
    ),

    # ── EMTALA / Medicare / Medicaid ──────────────────────────────
    AllowedCitation(
        canonical="42usc1395dd",
        display="42 U.S.C. § 1395dd",
        source_url=_usc(42, "1395dd"),
        origin="knowledge_base/02;policy_analyzer benchmark fallback (EMTALA)",
        aliases=("emtala", "emergency medical treatment and labor act"),
        note="EMTALA.",
    ),
    AllowedCitation(
        canonical="42usc1395y",
        display="42 U.S.C. § 1395y",
        source_url=_usc(42, "1395y"),
        origin="knowledge_base/04",
        aliases=("42usc1395y(b)",),
        note="Medicare exclusions from coverage / Medicare Secondary Payer (subsection (b)).",
    ),
    AllowedCitation(
        canonical="42usc1395n",
        display="42 U.S.C. § 1395n",
        source_url=_usc(42, "1395n"),
        origin="knowledge_base/04",
        note="Medicare Part B procedure for payment of claims.",
    ),
    AllowedCitation(
        canonical="42usc1320a-7",
        display="42 U.S.C. § 1320a-7",
        source_url=_usc(42, "1320a-7"),
        origin="knowledge_base/04",
        note="Exclusion of certain individuals and entities from Federal health care programs.",
    ),
    AllowedCitation(
        canonical="42usc1396k",
        display="42 U.S.C. § 1396k",
        source_url=_usc(42, "1396k"),
        origin="knowledge_base/05",
        note="Medicaid assignment of rights / third-party liability.",
    ),
    AllowedCitation(
        canonical="42cfr422",
        display="42 CFR Part 422",
        source_url=_ecfr_part(42, "422"),
        origin="regulatory_router (MEDICARE_ADVANTAGE_5LEVEL)",
        aliases=("42cfr422 subpart m", "42 cfr part 422 subpart m"),
        note="Medicare Advantage program — Subpart M grievances, organization determinations and appeals.",
    ),
    AllowedCitation(
        canonical="42cfr422.566",
        display="42 CFR § 422.566",
        source_url=_ecfr_section(42, "422.566"),
        origin="deadline_calculator (MA organization determinations)",
        note="MA organization determinations.",
    ),
    AllowedCitation(
        canonical="42cfr405",
        display="42 CFR Part 405, Subpart I",
        source_url=_ecfr_part(42, "405"),
        origin="regulatory_router (MEDICARE_ORIGINAL_5LEVEL)",
        aliases=("42cfr405, subpart i", "42 cfr part 405 subpart i"),
        note="Original Medicare determinations, redeterminations, reconsiderations and appeals.",
    ),
    AllowedCitation(
        canonical="42cfr405.1803",
        display="42 CFR § 405.1803",
        source_url=_ecfr_section(42, "405.1803"),
        origin="bill_auditor",
        note="Intermediary determination and notice of amount of program reimbursement.",
    ),
    AllowedCitation(
        canonical="42cfr438.402",
        display="42 CFR § 438.402",
        source_url=_ecfr_section(42, "438.402"),
        origin="regulatory_router;deadline_calculator (MEDICAID_FAIR_HEARING)",
        note="Managed Medicaid grievance and appeal system — general requirements.",
    ),
    AllowedCitation(
        canonical="42cfr431.200",
        display="42 CFR § 431.200",
        source_url=_ecfr_section(42, "431.200"),
        origin="regulatory_router (MEDICAID_FAIR_HEARING)",
        aliases=("42cfr431 subpart e",),
        note="Fair hearings for applicants and beneficiaries — basis and scope.",
    ),
    AllowedCitation(
        canonical="42cfr431.221",
        display="42 CFR § 431.221",
        source_url=_ecfr_section(42, "431.221"),
        origin="state_profiles (Medicaid fair hearing request window)",
        note="Request for a fair hearing — reasonable time, not to exceed 90 days.",
    ),

    # ── HIPAA ─────────────────────────────────────────────────────
    AllowedCitation(
        canonical="45cfr160",
        display="45 CFR Part 160",
        source_url=_ecfr_part(45, "160"),
        origin="knowledge_base/05",
        aliases=("hipaa",),
        note="HIPAA general administrative requirements.",
    ),
    AllowedCitation(
        canonical="45cfr164",
        display="45 CFR Part 164",
        source_url=_ecfr_part(45, "164"),
        origin="knowledge_base/05",
        aliases=("hipaa privacy rule", "hipaa security rule"),
        note="HIPAA security and privacy.",
    ),
    AllowedCitation(
        canonical="45cfr164.524",
        display="45 CFR § 164.524",
        source_url=_ecfr_section(45, "164.524"),
        origin="knowledge_base/05 (right of access to claim file)",
        note="Access of individuals to protected health information.",
    ),
    AllowedCitation(
        canonical="45cfr164.400",
        display="45 CFR § 164.400",
        source_url=_ecfr_section(45, "164.400"),
        origin="knowledge_base/05 (breach notification, Subpart D §§ 164.400-414)",
        aliases=("hipaa breach notification rule",),
        note="Notification in the case of breach of unsecured PHI — applicability (Subpart D).",
    ),

    # ── Fraud & abuse ─────────────────────────────────────────────
    AllowedCitation(
        canonical="42usc1395nn",
        display="42 U.S.C. § 1395nn",
        source_url=_usc(42, "1395nn"),
        origin="knowledge_base/04 (Stark Law)",
        aliases=("stark law", "physician self-referral law"),
        note="Limitation on certain physician referrals (Stark Law).",
    ),
    AllowedCitation(
        canonical="31usc3729",
        display="31 U.S.C. § 3729",
        source_url=_usc(31, "3729"),
        origin="knowledge_base/04 (False Claims Act, §§ 3729-3733)",
        aliases=("false claims act",),
        note="False Claims Act — liability for false claims.",
    ),
]

CITATION_ALLOWLIST: dict[str, AllowedCitation] = {e.canonical: e for e in _ENTRIES}

# Alias index: normalized-alias -> entry. Aliases are stored lowercase with single spaces.
ALIAS_INDEX: dict[str, AllowedCitation] = {}
for _e in _ENTRIES:
    for _a in _e.aliases:
        ALIAS_INDEX[" ".join(_a.lower().split())] = _e


def allowlist_needs_human_verification() -> bool:
    """True if ANY entry has not been human-verified yet."""
    return any(e.needs_human_verification or e.verified_on is None for e in _ENTRIES)


def unverified_entries() -> list[AllowedCitation]:
    return [e for e in _ENTRIES if e.needs_human_verification or e.verified_on is None]


def all_entries() -> list[AllowedCitation]:
    return list(_ENTRIES)


__all__ = [
    "AllowedCitation",
    "CITATION_ALLOWLIST",
    "ALIAS_INDEX",
    "allowlist_needs_human_verification",
    "unverified_entries",
    "all_entries",
]
