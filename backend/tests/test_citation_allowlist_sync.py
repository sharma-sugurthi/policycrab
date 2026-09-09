"""
Guards on the citation allowlist data module.

  1. Every entry is sourced (https URL) and either human-verified (valid past date)
     or explicitly flagged needs_human_verification=True. Silent unsourced entries fail.
  2. Every display string normalizes to its own canonical key; every alias resolves.
  3. Every statute literal asserted by the deterministic engines / prompts normalizes
     into the allowlist — code cannot instruct the LLM to cite something we cannot verify.
  4. If the repo-root knowledge_base/ exists (it does in CI), every CFR/USC/ERISA/ACA
     section mentioned there normalizes into the allowlist.
"""

import re
from datetime import date
from pathlib import Path

import pytest

from app.engine.citation_allowlist import CITATION_ALLOWLIST, ALIAS_INDEX, all_entries
from app.engine.citation_verifier import normalize_statute, _allowlist_lookup

REPO_ROOT = Path(__file__).resolve().parents[2]
KB_DIR = REPO_ROOT / "knowledge_base"

STATUTE_RE = re.compile(
    r"(\d{1,2}\s*(?:C\.?F\.?R\.?|U\.?S\.?C\.?)\s*(?:Part\s*)?§{0,2}\s*\d+[a-z]{0,2}(?:\.\d+)?(?:-\d+)?(?:\([a-z0-9]+\))*)"
    r"|((?:ERISA|ACA|PHSA|MHPAEA)\s*(?:Sec\.?|Section|§)\s*\d+[a-z]?(?:\([a-z0-9]+\))*)",
    re.IGNORECASE,
)


def test_allowlist_is_non_empty_and_keys_match_entries():
    assert len(CITATION_ALLOWLIST) >= 20
    for key, entry in CITATION_ALLOWLIST.items():
        assert key == entry.canonical


@pytest.mark.parametrize("entry", all_entries(), ids=lambda e: e.canonical)
def test_every_entry_is_sourced_and_verification_state_is_explicit(entry):
    assert entry.source_url.startswith("https://"), entry.canonical
    assert entry.display.strip(), entry.canonical
    assert entry.origin.strip(), "origin must say where in the codebase this is asserted"
    if entry.verified_on is None:
        assert entry.needs_human_verification is True, (
            f"{entry.canonical}: unverified entries must be flagged needs_human_verification=True"
        )
    else:
        parsed = date.fromisoformat(entry.verified_on)
        assert parsed <= date.today(), f"{entry.canonical}: verified_on is in the future"
        assert entry.needs_human_verification is False


@pytest.mark.parametrize("entry", all_entries(), ids=lambda e: e.canonical)
def test_display_normalizes_to_canonical(entry):
    key = normalize_statute(entry.display)
    # Some displays carry a parenthetical like "PHSA § 2719 (ACA § 2719)" — the first parse must match.
    assert key == entry.canonical, f"{entry.display!r} normalized to {key!r}"


def test_every_alias_resolves_to_its_entry():
    for alias, entry in ALIAS_INDEX.items():
        assert _allowlist_lookup(normalize_statute(alias)) is entry or ALIAS_INDEX.get(alias) is entry


CODE_ASSERTED_STATUTES = [
    # regulatory_router.get_appeal_framework_details
    "29 U.S.C. § 1132", "29 CFR § 2560.503-1", "ACA Section 2719", "42 CFR Part 422",
    "42 CFR Part 405", "45 CFR Part 149", "42 CFR § 438.402", "42 CFR § 431.200",
    "45 CFR § 147.136", "45 CFR § 156.122",
    # grievance.CARC_PRECEDENTS + prompt rules 13/14
    "ERISA Sec. 503", "ACA § 2719", "45 CFR 156.122(c)", "45 CFR § 156.110",
    # triage NSA rule, models/claim
    "45 CFR § 149.410(b)",
    # appeal_routes.LEVEL_CONFIGS
    "DOL Technical Release 2010-01",
    # bill_auditor
    "42 CFR § 405.1803",
    # carrier_intelligence
    "29 CFR § 2560.503-1(h)(3)(iv)",
]


@pytest.mark.parametrize("raw", CODE_ASSERTED_STATUTES)
def test_code_asserted_statutes_are_in_allowlist(raw):
    key = normalize_statute(raw)
    assert key, f"{raw!r} did not parse"
    assert _allowlist_lookup(key), f"{raw!r} ({key}) is asserted in code but missing from the allowlist"


def test_regulatory_router_framework_details_all_verifiable():
    from app.engine.regulatory_router import get_appeal_framework_details
    from app.models.enums import AppealFramework

    for fw in AppealFramework:
        details = get_appeal_framework_details(fw)
        for field in ("governing_law", "regulation"):
            text = str(details.get(field) or "")
            for m in STATUTE_RE.finditer(text):
                key = normalize_statute(m.group(0))
                assert key and _allowlist_lookup(key), f"{fw.value}.{field}: {m.group(0)!r} not in allowlist"


def test_knowledge_base_statutes_are_in_allowlist():
    if not KB_DIR.exists():
        pytest.skip("knowledge_base/ not present (not shipped in the production container)")
    missing = {}
    for md in sorted(KB_DIR.glob("*.md")):
        for m in STATUTE_RE.finditer(md.read_text(encoding="utf-8", errors="ignore")):
            raw = m.group(0)
            key = normalize_statute(raw)
            if not (key and _allowlist_lookup(key)):
                missing.setdefault(raw, set()).add(md.name)
    assert not missing, f"knowledge_base statutes missing from allowlist: {missing}"
