"""
Citation Grounding Verifier — deterministic, no LLM.

Checks that an LLM-drafted appeal letter only cites law that we can ground:

  Regulatory citations (AppealOutput.cited_regulations + inline statutes found in
  the letter body) must match one of:
    Tier A — the curated allowlist in app/engine/citation_allowlist.py
    Tier B — a knowledge-base concept_id that was actually retrieved for this case
    Tier C — literal text inside a knowledge-base chunk the LLM was actually shown

  Policy clause citations (AppealOutput.policy_citations) must appear in the
  policy-document chunks retrieved for this case — exact (normalized) substring
  first, then a fuzzy ratio, then a cross-page search to detect page drift.

Unverified citations are handled per settings.citation_unverified_policy:
  "annotate" (default) — insert a visible [VERIFY: ...] marker after the first
                         occurrence in the letter; original preserved.
  "strip"              — remove from cited_regulations and replace inline
                         occurrences with a bracketed placeholder.
  "off"                — report only.

Everything here is pure: same inputs → same outputs. Nothing raises to the caller
(run_citation_verification wraps each step defensively).
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass

from app.engine.citation_allowlist import (
    CITATION_ALLOWLIST,
    ALIAS_INDEX,
    allowlist_needs_human_verification,
)

logger = logging.getLogger(__name__)

VERIFIER_VERSION = "v1"
VERIFY_MARKER = " [VERIFY: not found in PolicyCrab's verified legal sources]"
STRIP_PLACEHOLDER = "[citation removed pending verification]"

# ── Statute normalization ─────────────────────────────────────────

# 29 CFR § 2560.503-1(h)(3)(iv)   /  45 C.F.R. Part 149  /  42 CFR 438.402
_CFR_RE = re.compile(
    r"(?P<title>\d{1,2})\s*c\.?\s*f\.?\s*r\.?\s*(?:part\s*)?(?:§+\s*)?"
    r"(?P<section>\d+(?:\.\d+)?(?:-\d+)?)(?P<paren>(?:\([a-z0-9]+\))*)",
    re.IGNORECASE,
)
# 29 U.S.C. § 1132(a)  /  42 USC 1395dd
_USC_RE = re.compile(
    r"(?P<title>\d{1,2})\s*u\.?\s*s\.?\s*c\.?\s*(?:§+\s*)?"
    r"(?P<section>\d+[a-z]{0,2}(?:-\d+)?)(?P<paren>(?:\([a-z0-9]+\))*)",
    re.IGNORECASE,
)
# ERISA § 503 / ERISA Section 502(a) / ACA Section 2719 / PHSA § 2719 / MHPAEA
_ACT_RE = re.compile(
    r"\b(?P<act>erisa|aca|phsa|nsa|mhpaea|ppaca)\b\)?\s*(?:sec\.?|section|§+)?\s*"
    r"(?P<section>\d{3,4}[a-z]?)(?P<paren>(?:\([a-z0-9]+\))*)",
    re.IGNORECASE,
)
# "Section 2719 of the Public Health Service Act" / "Affordable Care Act Section 2719"
_LONG_ACT_RE = re.compile(
    r"(?:section|§+)\s*(?P<section>\d{3,4}[a-z]?)\s+of\s+the\s+"
    r"(?P<act>public health service act|affordable care act|employee retirement income security act|no surprises act)",
    re.IGNORECASE,
)
_DOL_TR_RE = re.compile(r"technical release\s*(?P<num>\d{4}-\d{2})", re.IGNORECASE)

_ACT_CANON = {
    "erisa": "erisa",
    "employee retirement income security act": "erisa",
    "aca": "phsa",   # ACA §§ 27xx are codified as PHSA §§ 27xx — treat as one family
    "ppaca": "phsa",
    "affordable care act": "phsa",
    "phsa": "phsa",
    "public health service act": "phsa",
    "nsa": "nsa",
    "no surprises act": "nsa",
    "mhpaea": "mhpaea",
}


def _clean_paren(paren: str) -> str:
    return re.sub(r"\s+", "", (paren or "")).lower()


def normalize_statute(raw: str | None) -> str | None:
    """
    Reduce a citation string to a canonical key, or None if unparseable.

      "29 CFR § 2560.503-1"          -> "29cfr2560.503-1"
      "29 C.F.R. 2560.503-1(h)(3)"    -> "29cfr2560.503-1(h)(3)"
      "29 U.S.C. § 1132(a)"          -> "29usc1132(a)"
      "ERISA Section 503"            -> "erisa503"
      "ACA Section 2719" / "PHSA § 2719" -> "phsa2719"
      "DOL Technical Release 2010-01" -> "doltr2010-01"
    """
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()

    m = _CFR_RE.search(text)
    if m:
        return f"{int(m.group('title'))}cfr{m.group('section').lower()}{_clean_paren(m.group('paren'))}"

    m = _USC_RE.search(text)
    if m:
        return f"{int(m.group('title'))}usc{m.group('section').lower()}{_clean_paren(m.group('paren'))}"

    m = _LONG_ACT_RE.search(text)
    if m:
        act = _ACT_CANON[m.group("act").lower()]
        return f"{act}{m.group('section').lower()}"

    m = _ACT_RE.search(text)
    if m:
        act = _ACT_CANON[m.group("act").lower()]
        return f"{act}{m.group('section').lower()}{_clean_paren(m.group('paren'))}"

    m = _DOL_TR_RE.search(text)
    if m:
        return f"doltr{m.group('num')}"

    return None


def _base_key(key: str) -> str:
    """Strip trailing (a)(1) subsection parens so 29cfr2560.503-1(h) matches 29cfr2560.503-1."""
    return re.sub(r"(\([a-z0-9]+\))+$", "", key)


def _allowlist_lookup(key: str | None):
    if not key:
        return None
    if key in CITATION_ALLOWLIST:
        return CITATION_ALLOWLIST[key]
    base = _base_key(key)
    if base in CITATION_ALLOWLIST:
        return CITATION_ALLOWLIST[base]
    return ALIAS_INDEX.get(key) or ALIAS_INDEX.get(base)


def _alias_lookup_raw(raw: str):
    """Exact (case/space-insensitive) alias match on the raw string, for non-parseable names like case law."""
    if not raw:
        return None
    norm = re.sub(r"\s+", " ", raw.strip().lower())
    return ALIAS_INDEX.get(norm)


# ── Inline statute scan ───────────────────────────────────────────

_INLINE_PATTERNS = (_CFR_RE, _USC_RE, _LONG_ACT_RE, _ACT_RE, _DOL_TR_RE)


def scan_letter_for_inline_citations(letter: str | None) -> list[str]:
    """Return the distinct raw statute strings found in the letter body (document order)."""
    if not letter:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for pattern in _INLINE_PATTERNS:
        for m in pattern.finditer(letter):
            raw = m.group(0).strip()
            key = normalize_statute(raw) or raw.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(raw)
    return found


# ── Regulatory citation verification ──────────────────────────────

@dataclass
class _RegResult:
    verified: list[dict]
    unverified: list[dict]


def _norm_text(text: str) -> str:
    text = (text or "").replace("—", "-").replace("–", "-")
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace("§", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _chunk_contains_statute(key: str, chunks: list[dict]) -> bool:
    """Tier C — does any retrieved KB chunk literally cite this statute?"""
    base = _base_key(key)
    for chunk in chunks or []:
        content = chunk.get("full_content") or chunk.get("chunk_text") or ""
        if not content:
            continue
        for pattern in _INLINE_PATTERNS:
            for m in pattern.finditer(content):
                k = normalize_statute(m.group(0))
                if k and (k == key or _base_key(k) == base):
                    return True
    return False


def verify_regulatory_citations(
    citations: list[dict],
    retrieved_kb_chunks: list[dict],
    cited_knowledge_chunks: list[str],
) -> tuple[list[dict], list[dict]]:
    """
    Returns (annotated_citations, unverified_list).

    annotated_citations: each input citation dict copied with
        verification_status = VERIFIED | UNVERIFIED and verification_source.
    unverified_list: UnverifiedCitation-shaped dicts.
    """
    annotated: list[dict] = []
    unverified: list[dict] = []
    concept_ids = {str(c) for c in (cited_knowledge_chunks or [])}
    retrieved_ids = {str(c.get("concept_id")) for c in (retrieved_kb_chunks or []) if c.get("concept_id")}

    for cit in citations or []:
        if not isinstance(cit, dict):
            continue
        out = dict(cit)
        statute = str(cit.get("statute") or "")
        key = normalize_statute(statute)

        # Tier A — allowlist (parsed key or raw alias, e.g. case names)
        if _allowlist_lookup(key) or _alias_lookup_raw(statute):
            out["verification_status"] = "VERIFIED"
            out["verification_source"] = "allowlist"
            annotated.append(out)
            continue

        # Tier B — the citation IS a retrieved knowledge-base concept id
        if statute in concept_ids or statute in retrieved_ids:
            out["verification_status"] = "VERIFIED"
            out["verification_source"] = "kb_chunk"
            annotated.append(out)
            continue

        # Tier C — the statute text appears inside a retrieved chunk
        if key and _chunk_contains_statute(key, retrieved_kb_chunks):
            out["verification_status"] = "VERIFIED"
            out["verification_source"] = "retrieval_text"
            annotated.append(out)
            continue

        out["verification_status"] = "UNVERIFIED"
        out["verification_source"] = None
        annotated.append(out)
        unverified.append({
            "statute": statute,
            "reason": "NOT_IN_ALLOWLIST" if key else "UNPARSEABLE",
            "kind": "regulatory",
        })

    return annotated, unverified


def verify_inline_citations(
    letter: str | None,
    already_cited: list[dict],
    retrieved_kb_chunks: list[dict],
) -> tuple[list[str], list[dict]]:
    """
    Scan the letter body for statutes not present in cited_regulations and verify them.
    Returns (inline_found, unverified_inline).
    """
    inline = scan_letter_for_inline_citations(letter)
    listed_keys = set()
    for c in already_cited or []:
        k = normalize_statute(str((c or {}).get("statute") or ""))
        if k:
            listed_keys.add(_base_key(k))

    unverified: list[dict] = []
    for raw in inline:
        key = normalize_statute(raw)
        if not key:
            continue
        if _base_key(key) in listed_keys:
            continue  # already judged via cited_regulations
        if _allowlist_lookup(key) or _chunk_contains_statute(key, retrieved_kb_chunks):
            continue
        unverified.append({"statute": raw, "reason": "NOT_IN_ALLOWLIST", "kind": "inline_letter"})
    return inline, unverified


# ── Policy clause verification ────────────────────────────────────

def _best_fuzzy_ratio(needle: str, haystack: str) -> float:
    """Max SequenceMatcher ratio of needle against sliding windows of haystack."""
    if not needle or not haystack:
        return 0.0
    if needle in haystack:
        return 1.0
    n = len(needle)
    window = max(n, int(n * 1.2))
    stride = max(1, n // 4)
    best = 0.0
    if len(haystack) <= window:
        return difflib.SequenceMatcher(None, needle, haystack).ratio()
    for start in range(0, len(haystack) - window + 1, stride):
        ratio = difflib.SequenceMatcher(None, needle, haystack[start:start + window]).ratio()
        if ratio > best:
            best = ratio
            if best >= 0.999:
                break
    return best


def _token_overlap_ratio(needle: str, haystack: str) -> float:
    """Fraction of significant needle tokens (>=4 chars) present in the haystack."""
    tokens = [t for t in re.findall(r"[a-z0-9]+", needle) if len(t) >= 4]
    if not tokens:
        return 0.0
    hay_tokens = set(re.findall(r"[a-z0-9]+", haystack))
    hits = sum(1 for t in tokens if t in hay_tokens)
    return hits / len(tokens)


def verify_policy_citations(
    policy_citations: list[dict],
    policy_chunks: list[dict],
    threshold: float = 0.85,
) -> tuple[list[dict], list[dict]]:
    """
    Returns (annotated_policy_citations, unverified_clauses).
    Each annotated citation gets verification_status and match_ratio (additive keys).
    """
    annotated: list[dict] = []
    unverified: list[dict] = []
    chunks = [c for c in (policy_chunks or []) if isinstance(c, dict) and c.get("chunk_text")]

    for pc in policy_citations or []:
        if not isinstance(pc, dict):
            continue
        out = dict(pc)
        clause = _norm_text(str(pc.get("exact_clause_text") or ""))
        page = pc.get("page_number")
        if not clause:
            out["verification_status"] = "UNVERIFIED"
            annotated.append(out)
            unverified.append({
                "page_number": page, "exact_clause_text": "", "reason": "TEXT_NOT_FOUND",
            })
            continue

        same_page = [c for c in chunks if str(c.get("page_number")) == str(page)]

        # (1)+(2): same page — substring, then fuzzy / token overlap
        best_ratio, best_page = 0.0, None
        for c in same_page:
            hay = _norm_text(c.get("chunk_text", ""))
            ratio = max(_best_fuzzy_ratio(clause, hay), _token_overlap_ratio(clause, hay))
            if ratio > best_ratio:
                best_ratio, best_page = ratio, c.get("page_number")
        if best_ratio >= threshold:
            out["verification_status"] = "VERIFIED"
            out["match_ratio"] = round(best_ratio, 3)
            annotated.append(out)
            continue

        # (3): any page — detect page drift
        other_best, other_page = 0.0, None
        for c in chunks:
            if str(c.get("page_number")) == str(page):
                continue
            hay = _norm_text(c.get("chunk_text", ""))
            ratio = max(_best_fuzzy_ratio(clause, hay), _token_overlap_ratio(clause, hay))
            if ratio > other_best:
                other_best, other_page = ratio, c.get("page_number")

        out["verification_status"] = "UNVERIFIED"
        if other_best >= threshold:
            out["match_ratio"] = round(other_best, 3)
            annotated.append(out)
            unverified.append({
                "page_number": page, "exact_clause_text": pc.get("exact_clause_text"),
                "reason": "PAGE_MISMATCH", "best_match_page": other_page,
                "best_match_ratio": round(other_best, 3),
            })
            continue

        if not same_page:
            reason = "PAGE_NOT_RETRIEVED"
        elif best_ratio > 0.0:
            reason = "LOW_SIMILARITY"
        else:
            reason = "TEXT_NOT_FOUND"
        top_ratio = max(best_ratio, other_best)
        out["match_ratio"] = round(top_ratio, 3)
        annotated.append(out)
        unverified.append({
            "page_number": page, "exact_clause_text": pc.get("exact_clause_text"),
            "reason": reason,
            "best_match_page": (best_page if best_ratio >= other_best else other_page) if top_ratio > 0 else None,
            "best_match_ratio": round(top_ratio, 3) if top_ratio > 0 else None,
        })

    return annotated, unverified


# ── Scoring ───────────────────────────────────────────────────────

def compute_grounding_score(
    reg_verified: int,
    reg_total: int,
    pol_verified: int,
    pol_total: int,
    inline_unverified: int,
    letter_type: str = "payer_appeal",
) -> tuple[float, str, list[str]]:
    """Returns (score, status, flags)."""
    flags: list[str] = []
    if letter_type == "provider_correction":
        return 1.0, "N/A", flags

    components: list[tuple[float, float]] = []  # (weight, fraction)
    if reg_total > 0:
        components.append((0.6, reg_verified / reg_total))
    else:
        flags.append("NO_CITATIONS")
        components.append((0.6, 0.0))
    if pol_total > 0:
        components.append((0.4, pol_verified / pol_total))

    weight_sum = sum(w for w, _ in components)
    score = sum(w * f for w, f in components) / weight_sum if weight_sum else 0.0
    score -= 0.1 * min(max(inline_unverified, 0), 3)
    score = max(0.0, min(1.0, round(score, 3)))

    if score >= 0.95:
        status = "VERIFIED"
    elif score >= 0.5:
        status = "PARTIAL"
    else:
        status = "FAILED"
    return score, status, flags


# ── Letter mutation ───────────────────────────────────────────────

def _find_first(letter: str, statute: str) -> int:
    """Case-insensitive, whitespace-tolerant first index of statute in letter; -1 if absent."""
    if not statute:
        return -1
    idx = letter.lower().find(statute.lower())
    if idx >= 0:
        return idx
    # Tolerate whitespace / section-sign differences
    pat = re.escape(statute.strip())
    pat = pat.replace(r"\ ", r"\s*").replace(r"§", r"§?\s*")
    m = re.search(pat, letter, re.IGNORECASE)
    return m.start() if m else -1


def annotate_letter(letter: str, unverified: list[dict]) -> tuple[str, bool]:
    """Insert VERIFY_MARKER after the first occurrence of each unverified statute string."""
    if not letter or not unverified:
        return letter, False
    changed = False
    for item in unverified:
        statute = str(item.get("statute") or "")
        if not statute:
            continue
        idx = _find_first(letter, statute)
        if idx < 0:
            continue
        end = idx + len(statute)
        # If our regex path matched, recompute the true end via search
        m = re.search(re.escape(statute).replace(r"\ ", r"\s*"), letter[idx:], re.IGNORECASE)
        if m:
            end = idx + m.end()
        if letter[end:end + len(VERIFY_MARKER)] == VERIFY_MARKER:
            continue  # already annotated (idempotent)
        letter = letter[:end] + VERIFY_MARKER + letter[end:]
        changed = True
    return letter, changed


def strip_citations(letter: str, unverified: list[dict]) -> tuple[str, bool]:
    """Replace every occurrence of each unverified statute string with STRIP_PLACEHOLDER."""
    if not letter or not unverified:
        return letter, False
    changed = False
    for item in unverified:
        statute = str(item.get("statute") or "")
        if not statute:
            continue
        pat = re.escape(statute.strip()).replace(r"\ ", r"\s*")
        new_letter, n = re.subn(pat, STRIP_PLACEHOLDER, letter, flags=re.IGNORECASE)
        if n:
            letter, changed = new_letter, True
    return letter, changed


# ── Orchestrator used by the appeal_qa node ───────────────────────

def run_citation_verification(
    appeal_output: dict,
    knowledge_chunks: list[dict],
    policy_chunks: list[dict],
    policy_mode: str | None = None,
    fuzzy_threshold: float | None = None,
) -> tuple[dict, dict]:
    """
    Verify a full AppealOutput dict. Returns (citation_verification_dict, updated_appeal_output).

    The returned appeal_output is a copy with additive keys only:
      cited_regulations[*].verification_status / verification_source
      policy_citations[*].verification_status / match_ratio
      citation_verification, appeal_letter_unannotated (and appeal_letter if annotated/stripped)
    """
    from app.config import settings

    mode = (policy_mode or settings.citation_unverified_policy or "annotate").lower()
    if mode not in ("annotate", "strip", "off"):
        mode = "annotate"
    threshold = fuzzy_threshold if fuzzy_threshold is not None else settings.citation_policy_fuzzy_threshold

    out = dict(appeal_output)
    letter = str(out.get("appeal_letter") or "")
    letter_type = str(out.get("letter_type") or "payer_appeal")

    reg_annotated, reg_unverified = verify_regulatory_citations(
        out.get("cited_regulations") or [], knowledge_chunks, out.get("cited_knowledge_chunks") or []
    )
    inline_found, inline_unverified = verify_inline_citations(letter, reg_annotated, knowledge_chunks)
    pol_annotated, pol_unverified = verify_policy_citations(
        out.get("policy_citations") or [], policy_chunks, threshold=threshold
    )

    reg_total = len(reg_annotated)
    reg_verified = sum(1 for c in reg_annotated if c.get("verification_status") == "VERIFIED")
    pol_total = len(pol_annotated)
    pol_verified = sum(1 for c in pol_annotated if c.get("verification_status") == "VERIFIED")

    score, status, flags = compute_grounding_score(
        reg_verified, reg_total, pol_verified, pol_total, len(inline_unverified), letter_type
    )

    all_unverified = reg_unverified + inline_unverified
    if all_unverified and mode != "off" and letter_type != "provider_correction":
        if mode == "annotate":
            new_letter, changed = annotate_letter(letter, all_unverified)
            if changed:
                out["appeal_letter_unannotated"] = letter
                out["appeal_letter"] = new_letter
                flags.append("LETTER_ANNOTATED")
        elif mode == "strip":
            new_letter, changed = strip_citations(letter, all_unverified)
            if changed:
                out["appeal_letter_unannotated"] = letter
                out["appeal_letter"] = new_letter
                flags.append("CITATIONS_STRIPPED")
            out_regs = [c for c in reg_annotated if c.get("verification_status") == "VERIFIED"]
            reg_annotated = out_regs

    if allowlist_needs_human_verification():
        flags.append("ALLOWLIST_NEEDS_HUMAN_VERIFICATION")

    out["cited_regulations"] = reg_annotated
    out["policy_citations"] = pol_annotated

    verification = {
        "status": status,
        "verified_count": reg_verified + pol_verified,
        "total_count": reg_total + pol_total,
        "unverified": all_unverified,
        "unverified_policy_clauses": pol_unverified,
        "inline_citations_found": inline_found,
        "grounding_score": score,
        "flags": flags,
        "policy_applied": mode,
        "verifier_version": VERIFIER_VERSION,
    }
    out["citation_verification"] = verification

    logger.info(
        f"Citation verifier: status={status} score={score} "
        f"regs {reg_verified}/{reg_total}, clauses {pol_verified}/{pol_total}, "
        f"inline unverified={len(inline_unverified)}, mode={mode}"
    )
    return verification, out
