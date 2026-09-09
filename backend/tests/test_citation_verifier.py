"""
Unit tests for the deterministic citation grounding verifier.
No LLM, no Supabase, no network.
"""

import pytest

from app.engine import citation_verifier as cv
from app.engine.citation_verifier import (
    normalize_statute,
    scan_letter_for_inline_citations,
    verify_regulatory_citations,
    verify_inline_citations,
    verify_policy_citations,
    compute_grounding_score,
    annotate_letter,
    strip_citations,
    run_citation_verification,
    VERIFY_MARKER,
)


# ── Normalization ─────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("29 CFR § 2560.503-1", "29cfr2560.503-1"),
    ("29 C.F.R. 2560.503-1", "29cfr2560.503-1"),
    ("29 CFR §2560.503-1", "29cfr2560.503-1"),
    ("29 C.F.R. 2560.503-1(h)(3)(iv)", "29cfr2560.503-1(h)(3)(iv)"),
    ("45 CFR Part 149", "45cfr149"),
    ("45 CFR § 149.410(b)", "45cfr149.410(b)"),
    ("42 CFR § 438.402", "42cfr438.402"),
    ("29 U.S.C. § 1132", "29usc1132"),
    ("29 USC 1132(a)", "29usc1132(a)"),
    ("42 U.S.C. § 1395dd", "42usc1395dd"),
    ("42 U.S.C. § 1320a-7", "42usc1320a-7"),
    ("ERISA Section 503", "erisa503"),
    ("ERISA Sec. 503", "erisa503"),
    ("ERISA 503", "erisa503"),
    ("ERISA § 502(a)", "erisa502(a)"),
    ("ACA Section 2719", "phsa2719"),
    ("PHSA § 2719", "phsa2719"),
    ("Section 2719 of the Public Health Service Act", "phsa2719"),
    ("Affordable Care Act (ACA) § 2719", "phsa2719"),
    ("DOL Technical Release 2010-01", "doltr2010-01"),
])
def test_normalize_statute(raw, expected):
    assert normalize_statute(raw) == expected


@pytest.mark.parametrize("raw", ["Health Fairness Act of 2019", "", None, "Unknown", "NAIC Model Act"])
def test_normalize_statute_unparseable(raw):
    assert normalize_statute(raw) is None


# ── Regulatory citations: tiers ───────────────────────────────────

KB = [
    {"concept_id": "erisa_claims", "title": "ERISA", "full_content": "Under 29 CFR § 2560.503-1 plans must ..."},
    {"concept_id": "state_prompt_pay", "title": "Prompt pay", "full_content": "Texas Insurance Code § 1301.103 requires ..."},
]


def test_tier_a_allowlist_by_key_and_alias():
    cits = [
        {"statute": "29 CFR § 2560.503-1", "description": "", "relevance": ""},
        {"statute": "ERISA Section 503", "description": "", "relevance": ""},
        {"statute": "ERISA 503", "description": "", "relevance": ""},
    ]
    annotated, unverified = verify_regulatory_citations(cits, [], [])
    assert unverified == []
    assert all(c["verification_status"] == "VERIFIED" for c in annotated)
    assert all(c["verification_source"] == "allowlist" for c in annotated)


def test_tier_a_subsection_matches_base_entry():
    annotated, unverified = verify_regulatory_citations(
        [{"statute": "29 CFR § 2560.503-1(h)(3)(iv)", "description": "", "relevance": ""}], [], []
    )
    assert unverified == []
    assert annotated[0]["verification_status"] == "VERIFIED"


def test_tier_b_concept_id_fallback_citation():
    """grievance.py synthesizes citations whose statute IS the KB concept_id."""
    annotated, unverified = verify_regulatory_citations(
        [{"statute": "state_prompt_pay", "description": "", "relevance": ""}],
        KB, ["state_prompt_pay"],
    )
    assert unverified == []
    assert annotated[0]["verification_source"] == "kb_chunk"


def test_tier_c_statute_present_in_retrieved_chunk_text():
    kb = [{"concept_id": "x", "title": "x", "full_content": "See 45 CFR § 156.115 for EHB provision rules."}]
    # Use a statute that is deliberately absent from the allowlist key set? 156.115 IS in the allowlist,
    # so pick one only present in retrieval text:
    kb = [{"concept_id": "x", "title": "x", "full_content": "See 26 U.S.C. § 4980H employer mandate."}]
    annotated, unverified = verify_regulatory_citations(
        [{"statute": "26 U.S.C. § 4980H", "description": "", "relevance": ""}], kb, []
    )
    assert unverified == []
    assert annotated[0]["verification_source"] == "retrieval_text"


def test_fabricated_statute_is_unverified():
    annotated, unverified = verify_regulatory_citations(
        [{"statute": "50 CFR § 999.1", "description": "", "relevance": ""},
         {"statute": "Health Fairness Act of 2019", "description": "", "relevance": ""}],
        KB, [],
    )
    assert [u["reason"] for u in unverified] == ["NOT_IN_ALLOWLIST", "UNPARSEABLE"]
    assert all(c["verification_status"] == "UNVERIFIED" for c in annotated)


# ── Inline scan ───────────────────────────────────────────────────

def test_inline_scan_finds_statutes_in_prose():
    letter = (
        "Under 45 CFR 147.136 you must offer external review. ERISA Section 503 also applies. "
        "The fictional 50 CFR § 999.1 does not."
    )
    found = scan_letter_for_inline_citations(letter)
    keys = {normalize_statute(f) for f in found}
    assert {"45cfr147.136", "erisa503", "50cfr999.1"} <= keys


def test_inline_unverified_excludes_already_listed_and_allowlisted():
    letter = "Per 29 CFR § 2560.503-1 and the bogus 50 CFR § 999.1 ..."
    listed = [{"statute": "29 CFR § 2560.503-1"}]
    _, unverified = verify_inline_citations(letter, listed, [])
    assert [u["statute"] for u in unverified] == ["50 CFR § 999.1"]
    assert unverified[0]["kind"] == "inline_letter"


# ── Policy clause verification ────────────────────────────────────

CHUNKS = [
    {"page_number": 12, "chunk_index": 0, "section_heading": "BENEFITS",
     "chunk_text": "Section 4 — Covered Services. Joint replacement surgery is covered when medically necessary, "
                   "subject to prior authorization."},
    {"page_number": 30, "chunk_index": 0, "section_heading": "EXCLUSIONS",
     "chunk_text": "Cosmetic surgery is excluded from coverage under any circumstances."},
]


def test_policy_clause_exact_match():
    annotated, unverified = verify_policy_citations(
        [{"page_number": 12, "exact_clause_text": "Joint replacement surgery is covered when medically necessary"}],
        CHUNKS,
    )
    assert unverified == []
    assert annotated[0]["verification_status"] == "VERIFIED"
    assert annotated[0]["match_ratio"] == 1.0


def test_policy_clause_whitespace_and_dash_variants_match():
    annotated, unverified = verify_policy_citations(
        [{"page_number": 12, "exact_clause_text": "Section 4 -  Covered   Services. Joint replacement surgery is covered"}],
        CHUNKS,
    )
    assert unverified == []


def test_policy_clause_page_mismatch_reports_best_page():
    annotated, unverified = verify_policy_citations(
        [{"page_number": 13, "exact_clause_text": "Joint replacement surgery is covered when medically necessary"}],
        CHUNKS,
    )
    assert unverified[0]["reason"] == "PAGE_MISMATCH"
    assert unverified[0]["best_match_page"] == 12
    assert annotated[0]["verification_status"] == "UNVERIFIED"


def test_policy_clause_page_not_retrieved():
    annotated, unverified = verify_policy_citations(
        [{"page_number": 99, "exact_clause_text": "Completely different invented text about dental implants"}],
        CHUNKS,
    )
    assert unverified[0]["reason"] == "PAGE_NOT_RETRIEVED"


def test_policy_clause_fabricated_text_low_similarity():
    annotated, unverified = verify_policy_citations(
        [{"page_number": 12, "exact_clause_text": "All experimental treatments are fully covered without limit"}],
        CHUNKS,
    )
    assert unverified[0]["reason"] in ("LOW_SIMILARITY", "TEXT_NOT_FOUND")
    assert annotated[0]["verification_status"] == "UNVERIFIED"


def test_policy_clause_threshold_is_respected():
    clause = [{"page_number": 12, "exact_clause_text": "Joint replacement surgery is covered when medically needed"}]
    _, strict = verify_policy_citations(clause, CHUNKS, threshold=0.99)
    _, lenient = verify_policy_citations(clause, CHUNKS, threshold=0.70)
    assert strict and not lenient


# ── Scoring ───────────────────────────────────────────────────────

def test_grounding_score_arithmetic_and_status():
    score, status, flags = compute_grounding_score(2, 2, 1, 1, 0)
    assert (score, status, flags) == (1.0, "VERIFIED", [])

    score, status, _ = compute_grounding_score(1, 2, 0, 0, 0)
    assert score == 0.5 and status == "PARTIAL"

    score, status, _ = compute_grounding_score(1, 2, 1, 1, 1)   # 0.6*0.5 + 0.4*1.0 = 0.7 ; -0.1 inline
    assert score == pytest.approx(0.6) and status == "PARTIAL"

    score, status, flags = compute_grounding_score(0, 0, 0, 0, 0)
    assert score == 0.0 and status == "FAILED" and "NO_CITATIONS" in flags


def test_grounding_score_provider_correction_is_not_applicable():
    assert compute_grounding_score(0, 0, 0, 0, 0, letter_type="provider_correction") == (1.0, "N/A", [])


def test_grounding_score_inline_penalty_caps_at_three():
    a, _, _ = compute_grounding_score(2, 2, 0, 0, 3)
    b, _, _ = compute_grounding_score(2, 2, 0, 0, 10)
    assert a == b == pytest.approx(0.7)


# ── Letter mutation ───────────────────────────────────────────────

def test_annotate_inserts_marker_once_and_is_idempotent():
    letter = "This violates 50 CFR § 999.1. Again, 50 CFR § 999.1 is clear."
    new, changed = annotate_letter(letter, [{"statute": "50 CFR § 999.1"}])
    assert changed
    assert new.count(VERIFY_MARKER) == 1
    assert new.startswith("This violates 50 CFR § 999.1" + VERIFY_MARKER)
    again, changed2 = annotate_letter(new, [{"statute": "50 CFR § 999.1"}])
    assert not changed2 and again == new


def test_annotate_leaves_letter_alone_when_statute_absent():
    letter = "No statutes here."
    new, changed = annotate_letter(letter, [{"statute": "50 CFR § 999.1"}])
    assert not changed and new == letter


def test_strip_replaces_every_occurrence():
    letter = "See 50 CFR § 999.1 and again 50 CFR § 999.1."
    new, changed = strip_citations(letter, [{"statute": "50 CFR § 999.1"}])
    assert changed and "50 CFR" not in new and new.count(cv.STRIP_PLACEHOLDER) == 2


# ── Orchestrator ──────────────────────────────────────────────────

def _appeal(letter, regs, pcs=None):
    return {
        "appeal_letter": letter,
        "letter_type": "payer_appeal",
        "cited_regulations": regs,
        "cited_knowledge_chunks": ["erisa_claims"],
        "policy_citations": pcs or [],
    }


def test_run_verification_annotate_mode_preserves_original():
    letter = "Under 29 CFR § 2560.503-1 and the Health Fairness Act of 2019 (50 CFR § 999.1) you must pay."
    regs = [
        {"statute": "29 CFR § 2560.503-1", "description": "", "relevance": ""},
        {"statute": "50 CFR § 999.1", "description": "", "relevance": ""},
    ]
    verification, out = run_citation_verification(_appeal(letter, regs), KB, [], policy_mode="annotate")

    assert verification["status"] == "PARTIAL"
    assert verification["grounding_score"] == 0.5
    assert [u["statute"] for u in verification["unverified"]] == ["50 CFR § 999.1"]
    assert "LETTER_ANNOTATED" in verification["flags"]
    assert out["appeal_letter_unannotated"] == letter
    assert VERIFY_MARKER in out["appeal_letter"]
    assert out["cited_regulations"][0]["verification_status"] == "VERIFIED"
    assert out["cited_regulations"][1]["verification_status"] == "UNVERIFIED"
    assert out["citation_verification"]["verifier_version"] == "v1"


def test_run_verification_strip_mode_removes_unverified():
    letter = "Cite 50 CFR § 999.1 here."
    regs = [{"statute": "50 CFR § 999.1", "description": "", "relevance": ""}]
    verification, out = run_citation_verification(_appeal(letter, regs), KB, [], policy_mode="strip")
    assert "CITATIONS_STRIPPED" in verification["flags"]
    assert out["cited_regulations"] == []
    assert cv.STRIP_PLACEHOLDER in out["appeal_letter"]


def test_run_verification_off_mode_reports_only():
    letter = "Cite 50 CFR § 999.1 here."
    regs = [{"statute": "50 CFR § 999.1", "description": "", "relevance": ""}]
    verification, out = run_citation_verification(_appeal(letter, regs), KB, [], policy_mode="off")
    assert out["appeal_letter"] == letter
    assert "appeal_letter_unannotated" not in out
    assert verification["unverified"]


def test_run_verification_provider_correction_not_applicable():
    ao = _appeal("Dear Billing Department, please add modifier 25.", [])
    ao["letter_type"] = "provider_correction"
    verification, out = run_citation_verification(ao, [], [], policy_mode="annotate")
    assert verification["status"] == "N/A" and verification["grounding_score"] == 1.0
    assert out["appeal_letter"] == ao["appeal_letter"]


def test_run_verification_with_policy_clauses_and_page_drift():
    letter = "On page 13 of the policy, it states: Joint replacement surgery is covered when medically necessary."
    regs = [{"statute": "29 CFR § 2560.503-1", "description": "", "relevance": ""}]
    pcs = [{"page_number": 13, "exact_clause_text": "Joint replacement surgery is covered when medically necessary"}]
    verification, out = run_citation_verification(_appeal(letter, regs, pcs), KB, CHUNKS, policy_mode="annotate")
    assert verification["unverified_policy_clauses"][0]["reason"] == "PAGE_MISMATCH"
    assert verification["unverified_policy_clauses"][0]["best_match_page"] == 12
    assert verification["grounding_score"] == pytest.approx(0.6)   # regs 1/1 * .6 + clauses 0/1 * .4
