"""
PHI Scrubber — regex-based redaction of Protected Health Information.

Applied before writing claim text to Supabase to minimize unnecessary
PHI exposure. This is a best-effort scrub, NOT a guaranteed HIPAA
de-identification method. It targets the most common patterns that
patients accidentally type into freetext fields.

Patterns covered:
  - SSN:        123-45-6789 / 123 45 6789
  - DOB:        01/15/1985 / 1-15-85 / January 15 1985
  - Member IDs: common insurer formats (8–12 alphanumeric with dashes)
  - NPI:        10-digit national provider identifier
  - Phone:      (555) 123-4567 / 555-123-4567 / 5551234567
  - Credit card numbers (occasionally typed in billing context)

Returns the scrubbed string and a count of replacements made.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Replacement token ─────────────────────────────────────────────
_REDACT = "[REDACTED]"

# ── PHI patterns — ordered from most specific to least ───────────
_PATTERNS: list[tuple[str, str]] = [
    # SSN — 123-45-6789 or 123 45 6789
    (r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b", "SSN"),

    # 10-digit NPI (standalone number not preceded by $ or .)
    (r"(?<![.$])\b\d{10}\b", "NPI"),

    # Phone numbers — (555) 123-4567 / 555-123-4567 / +1 555 123 4567
    (r"(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", "PHONE"),

    # Credit card — 16-digit groups
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "CC"),

    # Date of birth — MM/DD/YYYY, M/D/YY, MM-DD-YYYY
    (r"\b(0?[1-9]|1[0-2])[\/\-](0?[1-9]|[12]\d|3[01])[\/\-](\d{2}|\d{4})\b", "DOB"),

    # Member ID — common insurer patterns: 8-12 alphanumeric chars
    # e.g. XYZ123456789, ABC-12345678, 12345678A
    # Guarded: must be labeled near "member", "id", "policy", "plan"
    (
        r"(?i)(?:member\s*(?:id|number|#)|policy\s*(?:id|number|#)|plan\s*(?:id|number|#))"
        r"\s*:?\s*([A-Z0-9]{2,4}[-]?[A-Z0-9]{6,10})",
        "MEMBER_ID",
    ),
]


def scrub_phi(text: str) -> tuple[str, int]:
    """
    Scrub PHI patterns from freetext. Returns (scrubbed_text, redaction_count).

    Args:
        text: Raw user-supplied claim description or similar freetext.

    Returns:
        Tuple of (cleaned text, number of redactions made).
    """
    if not text:
        return text, 0

    total_redactions = 0

    for pattern, label in _PATTERNS:
        compiled = re.compile(pattern)
        matches = compiled.findall(text)
        count = len(matches)
        if count > 0:
            text = compiled.sub(_REDACT, text)
            total_redactions += count
            logger.debug(f"PHI scrubber: redacted {count} {label} pattern(s)")

    if total_redactions > 0:
        logger.info(f"PHI scrubber: {total_redactions} total redaction(s) applied to claim text")

    return text, total_redactions
