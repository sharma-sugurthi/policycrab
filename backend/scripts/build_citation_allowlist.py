"""
Citation allowlist maintenance helper (never runs in production).

Usage (from backend/):
  python scripts/build_citation_allowlist.py --checklist
      Print every allowlist entry that still needs human verification, with its
      source_url, so a maintainer can open each page and set verified_on.

  python scripts/build_citation_allowlist.py --scan
      Regex-scan ../knowledge_base/*.md and the backend code for statute
      strings and report any that do NOT normalize into the allowlist.
      Use this after adding knowledge-base content.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.engine.citation_allowlist import all_entries, unverified_entries  # noqa: E402
from app.engine.citation_verifier import normalize_statute, _allowlist_lookup  # noqa: E402

STATUTE_RE = re.compile(
    r"(\d{1,2}\s*(?:C\.?F\.?R\.?|U\.?S\.?C\.?)\s*(?:Part\s*)?§{0,2}\s*\d+[a-z]{0,2}(?:\.\d+)?(?:-\d+)?(?:\([a-z0-9]+\))*)"
    r"|((?:ERISA|ACA|PHSA|MHPAEA|NSA)\s*(?:Sec\.?|Section|§)\s*\d+[a-z]?(?:\([a-z0-9]+\))*)"
    r"|(Technical Release\s*\d{4}-\d{2})",
    re.IGNORECASE,
)


def cmd_checklist() -> int:
    pending = unverified_entries()
    total = len(all_entries())
    print(f"Allowlist entries: {total}. Awaiting human verification: {len(pending)}\n")
    for e in pending:
        print(f"[ ] {e.display}")
        print(f"    open:   {e.source_url}")
        print(f"    claims: {e.note}")
        print(f"    origin: {e.origin}\n")
    print("After confirming each page, set verified_on='YYYY-MM-DD' and needs_human_verification=False "
          "in app/engine/citation_allowlist.py, then run pytest tests/test_citation_allowlist_sync.py.")
    return 0


def _scan_files() -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    targets: list[Path] = []
    kb = REPO_DIR / "knowledge_base"
    if kb.exists():
        targets.extend(sorted(kb.glob("*.md")))
    targets.extend(sorted((BACKEND_DIR / "app").rglob("*.py")))
    for path in targets:
        if path.name == "citation_allowlist.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in STATUTE_RE.finditer(text):
            hits.append((str(path.relative_to(REPO_DIR)), m.group(0).strip()))
    return hits


def cmd_scan() -> int:
    missing: dict[str, set[str]] = {}
    seen = 0
    for rel, raw in _scan_files():
        seen += 1
        key = normalize_statute(raw)
        if key and _allowlist_lookup(key):
            continue
        missing.setdefault(raw, set()).add(rel)
    print(f"Scanned {seen} statute mentions.")
    if not missing:
        print("All mentions normalize into the allowlist.")
        return 0
    print(f"{len(missing)} mention(s) NOT in the allowlist (add with a source_url, or leave to be flagged):\n")
    for raw, files in sorted(missing.items()):
        print(f"  {raw!r:45}  <- {', '.join(sorted(files))}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checklist", action="store_true", help="print human-verification checklist")
    parser.add_argument("--scan", action="store_true", help="scan KB + code for statutes missing from the allowlist")
    args = parser.parse_args()
    if not (args.checklist or args.scan):
        parser.print_help()
        return 0
    rc = 0
    if args.checklist:
        rc |= cmd_checklist()
    if args.scan:
        rc |= cmd_scan()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
