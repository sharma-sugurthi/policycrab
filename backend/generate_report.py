"""
PolicyCrab Benchmark Report Generator
--------------------------------------
Reads benchmark_results.json produced by pytest --json-report
and generates a premium, self-contained HTML validation report.

Usage:
    python3 generate_report.py
Output:
    benchmark_report.html
"""

import json
import re
from datetime import datetime
from pathlib import Path

DATA_FILE = Path("benchmark_results.json")
OUTPUT_FILE = Path("benchmark_report.html")

# ── Category mapping from test file names ────────────────────────
CATEGORY_MAP = {
    "test_cost_calculator":   ("💰", "Cost Calculator",        "Deterministic deductible/coinsurance/OOP waterfall math"),
    "test_grievance":         ("⚖️",  "Grievance Agent",         "AI appeal letter routing and drafting"),
    "test_triage":            ("🔀", "Triage Engine",           "Claim routing: provider error vs payer denial"),
    "test_policy_ingestion":  ("📄", "Policy Ingestion",        "SBC/EOB extraction and schema normalization"),
    "test_regulatory_router": ("🏛️", "Regulatory Router",       "ERISA / ACA / NSA / Medicare framework routing"),
    "test_eob_extractor":     ("🧾", "EOB Extractor",           "Explanation of Benefits parsing accuracy"),
    "test_deadline_calculator":("📅","Deadline Calculator",     "Appeal deadline computation by plan type"),
    "test_security_controls": ("🔒", "Security Controls",       "PHI scrubbing and access-control enforcement"),
    "test_claim_graph":       ("🤖", "Claim Agent Graph",       "LangGraph orchestration and state transitions"),
    "test_claim_intake":      ("📥", "Claim Intake",            "Claim form parsing and field normalization"),
    "test_policy_analyzer":   ("🔍", "Policy Analyzer",         "Cross-document contradiction detection"),
    "test_policy_extraction": ("📑", "Policy Extraction",       "Field-level policy data extraction"),
    "test_chunking":          ("✂️",  "Document Chunking",       "Heading-aware RAG chunking pipeline"),
    "test_user_data":         ("👤", "User Data Layer",         "Supabase policy/claim persistence"),
    "test_user_data_chat":    ("💬", "Chat Persistence",        "Multi-thread chat session storage"),
    "test_llm_health":        ("🩺", "LLM Health Check",        "Multi-provider model availability"),
    "test_llm_router":        ("⚡", "LLM Router",              "Fast vs high-compute model routing"),
    "test_embed":             ("🧠", "Embedding Engine",        "Vector embedding generation"),
    "test_smoke":             ("🔥", "Smoke Tests",             "Application startup and basic routes"),
    "test_api_security":      ("🛡️", "API Security",            "Authentication and authorization guards"),
    "test_cpt_icd_lookup":    ("🏥", "CPT/ICD Lookup",         "Medical code validation"),
    "test_synthetic_e2e":     ("🔄", "E2E Pipeline",            "Full claim → appeal pipeline (live AI)"),
}

def get_category(nodeid: str) -> tuple:
    for key, val in CATEGORY_MAP.items():
        if key in nodeid:
            return val
    return ("🧪", "Other", "Miscellaneous tests")

def parse_test_name(nodeid: str) -> str:
    """Convert test node ID to human-readable name."""
    # e.g. tests/test_cost_calculator.py::TestOOPMaxCap::test_oop_already_maxed
    parts = nodeid.split("::")
    raw = parts[-1]
    # Remove test_ prefix and convert underscores to spaces
    name = re.sub(r'^test_', '', raw)
    name = name.replace("_", " ").title()
    # Include class name for context if present
    if len(parts) == 3:
        cls = parts[1].replace("Test", "").replace("_", " ")
        name = f"{cls} — {name}"
    return name

def get_duration(test: dict) -> float:
    """Extract total test duration in seconds."""
    total = 0.0
    for phase in ("setup", "call", "teardown"):
        phase_data = test.get(phase, {})
        if phase_data:
            total += phase_data.get("duration", 0.0)
    return total

def main():
    if not DATA_FILE.exists():
        print(f"Error: {DATA_FILE} not found. Run pytest --json-report first.")
        return

    data = json.load(DATA_FILE.open())
    tests = data.get("tests", [])
    total_duration = data.get("duration", 0.0)
    run_ts = datetime.fromtimestamp(data.get("created", datetime.now().timestamp()))
    env = data.get("environment", {})

    # ── Aggregate by category ─────────────────────────────────────
    categories = {}
    passed = skipped = failed = 0
    
    for t in tests:
        outcome = t.get("outcome", "unknown")
        icon, cat_name, cat_desc = get_category(t["nodeid"])
        
        if cat_name not in categories:
            categories[cat_name] = {
                "icon": icon, "desc": cat_desc,
                "tests": [], "passed": 0, "failed": 0, "skipped": 0,
            }
        
        duration = get_duration(t)
        human_name = parse_test_name(t["nodeid"])
        
        # Get failure/skip message
        message = ""
        call_data = t.get("call", {})
        if call_data and call_data.get("longrepr"):
            raw = str(call_data["longrepr"])
            # Truncate to first 300 chars for display
            message = raw[:300].replace("<", "&lt;").replace(">", "&gt;")
            if len(raw) > 300:
                message += "..."

        setup_data = t.get("setup", {})
        if not message and setup_data and setup_data.get("longrepr"):
            raw = str(setup_data["longrepr"])
            message = raw[:300].replace("<", "&lt;").replace(">", "&gt;")

        categories[cat_name]["tests"].append({
            "name": human_name,
            "outcome": outcome,
            "duration": duration,
            "message": message,
        })

        if outcome == "passed":
            categories[cat_name]["passed"] += 1
            passed += 1
        elif outcome == "failed":
            categories[cat_name]["failed"] += 1
            failed += 1
        elif outcome == "skipped":
            categories[cat_name]["skipped"] += 1
            skipped += 1

    total = passed + failed + skipped
    accuracy = round((passed / total) * 100, 1) if total > 0 else 0

    # ── Build HTML ────────────────────────────────────────────────
    cat_cards_html = ""
    for cat_name, cat in sorted(categories.items(), key=lambda x: -x[1]["passed"]):
        cat_total = cat["passed"] + cat["failed"] + cat["skipped"]
        cat_pct = round((cat["passed"] / cat_total) * 100) if cat_total > 0 else 0
        status_color = "#10b981" if cat["failed"] == 0 else "#ef4444"
        ring_color = "#10b981" if cat["failed"] == 0 else "#ef4444"
        
        rows_html = ""
        for t in cat["tests"]:
            if t["outcome"] == "passed":
                badge = '<span class="badge pass">✓ PASS</span>'
            elif t["outcome"] == "failed":
                badge = '<span class="badge fail">✗ FAIL</span>'
            else:
                badge = '<span class="badge skip">⊘ SKIP</span>'
            
            msg_html = f'<div class="err-msg">{t["message"]}</div>' if t["message"] else ""
            dur = f'{t["duration"]*1000:.1f}ms' if t["duration"] < 1 else f'{t["duration"]:.2f}s'
            
            rows_html += f"""
            <div class="test-row {t['outcome']}">
                <div class="test-name">{t['name']}</div>
                <div class="test-meta">
                    {badge}
                    <span class="test-dur">{dur}</span>
                </div>
                {msg_html}
            </div>"""

        cat_cards_html += f"""
        <div class="cat-card {'all-pass' if cat['failed'] == 0 else 'has-fail'}">
            <div class="cat-header">
                <div class="cat-icon">{cat['icon']}</div>
                <div class="cat-info">
                    <div class="cat-name">{cat_name}</div>
                    <div class="cat-desc">{cat['desc']}</div>
                </div>
                <div class="cat-ring" style="--pct:{cat_pct};--color:{ring_color}">
                    <svg viewBox="0 0 36 36">
                        <circle cx="18" cy="18" r="15.9" fill="none" stroke="#1e293b" stroke-width="3"/>
                        <circle cx="18" cy="18" r="15.9" fill="none"
                            stroke="{ring_color}" stroke-width="3"
                            stroke-dasharray="{cat_pct} {100-cat_pct}"
                            stroke-dashoffset="25"
                            stroke-linecap="round"/>
                    </svg>
                    <span class="ring-pct" style="color:{ring_color}">{cat_pct}%</span>
                </div>
            </div>
            <div class="cat-pills">
                <span class="pill green">{cat['passed']} passed</span>
                {'<span class="pill red">' + str(cat['failed']) + ' failed</span>' if cat['failed'] else ''}
                {'<span class="pill gray">' + str(cat['skipped']) + ' skipped</span>' if cat['skipped'] else ''}
            </div>
            <div class="test-list">{rows_html}</div>
        </div>"""

    python_ver = env.get("Python", "3.12")
    platform = env.get("Platform", "Linux")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>PolicyCrab — Benchmark Validation Report</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap');
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg:#050507;--bg2:#0c0d11;--bg3:#111318;--border:#1e2030;
  --text:#f1f5f9;--text2:#94a3b8;--text3:#64748b;
  --accent:#e11d48;--accent2:#f43f5e;--green:#10b981;--red:#ef4444;--gray:#475569;
  --shadow:0 4px 24px rgba(0,0,0,.5);
}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);line-height:1.6;min-height:100vh}}

/* ── Header ── */
.header{{
  background:linear-gradient(135deg,#0a0010 0%,#050507 50%,#0a000a 100%);
  border-bottom:1px solid var(--border);
  padding:3rem 2rem 2rem;
  text-align:center;
  position:relative;
  overflow:hidden;
}}
.header-glow{{
  position:absolute;top:-200px;left:50%;transform:translateX(-50%);
  width:800px;height:500px;
  background:radial-gradient(circle,rgba(225,29,72,.18) 0%,transparent 70%);
  pointer-events:none;
}}
.logo-row{{display:flex;align-items:center;justify-content:center;gap:1rem;margin-bottom:1rem}}
.logo-badge{{
  display:inline-flex;align-items:center;gap:.5rem;
  padding:.375rem 1rem;background:rgba(225,29,72,.12);
  border:1px solid rgba(225,29,72,.3);border-radius:9999px;
  color:#fca5a5;font-size:.75rem;font-weight:600;
}}
.logo-dot{{width:8px;height:8px;border-radius:50%;background:#e11d48;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{box-shadow:0 0 0 0 rgba(225,29,72,.5)}}50%{{box-shadow:0 0 0 5px rgba(225,29,72,0)}}}}
h1{{font-size:clamp(1.75rem,4vw,3rem);font-weight:900;letter-spacing:-.04em;margin-bottom:.5rem}}
.gradient{{
  background:linear-gradient(135deg,#e11d48,#f43f5e,#fb923c);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.subtitle{{font-size:1rem;color:var(--text2);max-width:560px;margin:0 auto 2rem}}

/* ── Summary Cards ── */
.summary{{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:1.25rem;max-width:1100px;margin:0 auto 3rem;padding:0 2rem;
}}
.s-card{{
  background:var(--bg2);border:1px solid var(--border);
  border-radius:1.25rem;padding:1.5rem;text-align:center;
  transition:transform .2s ease,border-color .2s ease;
}}
.s-card:hover{{transform:translateY(-3px);border-color:#334155}}
.s-val{{font-size:2.5rem;font-weight:900;letter-spacing:-.03em;margin-bottom:.25rem}}
.s-label{{font-size:.8125rem;color:var(--text2);font-weight:500}}
.s-val.green{{color:var(--green)}}
.s-val.red{{color:var(--red)}}
.s-val.accent{{
  background:linear-gradient(135deg,#e11d48,#fb923c);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}

/* ── Meta row ── */
.meta-row{{
  display:flex;flex-wrap:wrap;justify-content:center;gap:1rem;
  max-width:900px;margin:0 auto 3rem;padding:0 2rem;
  font-size:.8125rem;color:var(--text3);
}}
.meta-chip{{
  display:flex;align-items:center;gap:.375rem;
  padding:.375rem .875rem;background:var(--bg2);
  border:1px solid var(--border);border-radius:9999px;
  font-family:'JetBrains Mono',monospace;font-size:.75rem;
}}

/* ── Category cards ── */
.cats{{max-width:1100px;margin:0 auto;padding:0 2rem 4rem;display:flex;flex-direction:column;gap:1.5rem}}

.cat-card{{
  background:var(--bg2);border:1px solid var(--border);
  border-radius:1.25rem;overflow:hidden;
  transition:border-color .2s ease;
}}
.cat-card.all-pass{{border-color:#052e16}}
.cat-card.has-fail{{border-color:#2d0a14}}
.cat-card:hover{{border-color:#334155}}

.cat-header{{
  display:flex;align-items:center;gap:1rem;
  padding:1.25rem 1.5rem;cursor:pointer;
  background:var(--bg3);
  border-bottom:1px solid var(--border);
  user-select:none;
}}
.cat-icon{{font-size:1.75rem;flex-shrink:0}}
.cat-info{{flex:1;min-width:0}}
.cat-name{{font-size:1rem;font-weight:700;color:var(--text)}}
.cat-desc{{font-size:.8125rem;color:var(--text2);margin-top:.125rem}}
.cat-ring{{position:relative;width:52px;height:52px;flex-shrink:0}}
.cat-ring svg{{transform:rotate(-90deg)}}
.ring-pct{{
  position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:.625rem;font-weight:800;font-family:'JetBrains Mono',monospace;
}}
.cat-pills{{display:flex;gap:.5rem;flex-wrap:wrap;padding:.875rem 1.5rem;border-bottom:1px solid var(--border)}}
.pill{{
  display:inline-flex;align-items:center;gap:.25rem;
  padding:.2rem .625rem;border-radius:9999px;
  font-size:.6875rem;font-weight:700;font-family:'JetBrains Mono',monospace;
}}
.pill.green{{background:rgba(16,185,129,.12);color:#10b981;border:1px solid rgba(16,185,129,.25)}}
.pill.red{{background:rgba(239,68,68,.12);color:#ef4444;border:1px solid rgba(239,68,68,.25)}}
.pill.gray{{background:rgba(71,85,105,.15);color:#94a3b8;border:1px solid rgba(71,85,105,.25)}}

/* ── Test rows ── */
.test-list{{padding:.75rem 1.5rem;display:flex;flex-direction:column;gap:.375rem}}
.test-row{{
  display:flex;flex-direction:column;gap:.25rem;
  padding:.75rem;border-radius:.75rem;
  transition:background .15s ease;
}}
.test-row:hover{{background:rgba(255,255,255,.02)}}
.test-row.passed .test-name{{color:var(--text)}}
.test-row.failed .test-name{{color:#fca5a5}}
.test-row.skipped .test-name{{color:var(--text3)}}
.test-meta{{display:flex;align-items:center;gap:.625rem;margin-top:.25rem}}
.test-name{{font-size:.875rem;font-weight:500;line-height:1.4}}
.test-dur{{font-size:.6875rem;color:var(--text3);font-family:'JetBrains Mono',monospace}}
.badge{{
  display:inline-flex;align-items:center;padding:.15rem .5rem;
  border-radius:.375rem;font-size:.625rem;font-weight:800;
  font-family:'JetBrains Mono',monospace;letter-spacing:.04em;
}}
.badge.pass{{background:rgba(16,185,129,.12);color:#10b981}}
.badge.fail{{background:rgba(239,68,68,.12);color:#ef4444}}
.badge.skip{{background:rgba(71,85,105,.15);color:#94a3b8}}
.err-msg{{
  font-size:.75rem;color:#fca5a5;font-family:'JetBrains Mono',monospace;
  background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.15);
  border-radius:.5rem;padding:.5rem .75rem;margin-top:.375rem;
  white-space:pre-wrap;word-break:break-word;
}}

/* ── Footer ── */
.footer{{
  text-align:center;padding:2rem;color:var(--text3);
  font-size:.75rem;border-top:1px solid var(--border);
}}

@media(max-width:600px){{
  .summary{{grid-template-columns:1fr 1fr}}
  .cat-header{{flex-wrap:wrap}}
  .cat-ring{{display:none}}
}}
</style>
</head>
<body>

<div class="header">
  <div class="header-glow"></div>
  <div class="logo-row">
    <div class="logo-badge"><span class="logo-dot"></span> Validation Report</div>
  </div>
  <h1>PolicyCrab<br/><span class="gradient">Benchmark Suite</span></h1>
  <p class="subtitle">
    Full automated validation of the deterministic adjudication engine,
    multi-agent orchestration, regulatory RAG pipeline, and security controls.
  </p>
</div>

<div class="summary">
  <div class="s-card">
    <div class="s-val accent">{total}</div>
    <div class="s-label">Total Test Cases</div>
  </div>
  <div class="s-card">
    <div class="s-val green">{passed}</div>
    <div class="s-label">Passed</div>
  </div>
  <div class="s-card">
    <div class="s-val {'red' if failed > 0 else 'green'}">{failed}</div>
    <div class="s-label">Failed</div>
  </div>
  <div class="s-card">
    <div class="s-val" style="color:#94a3b8">{skipped}</div>
    <div class="s-label">Skipped</div>
  </div>
  <div class="s-card">
    <div class="s-val accent">{accuracy}%</div>
    <div class="s-label">Pass Rate</div>
  </div>
  <div class="s-card">
    <div class="s-val" style="font-size:1.75rem;color:#94a3b8">{total_duration:.1f}s</div>
    <div class="s-label">Total Duration</div>
  </div>
</div>

<div class="meta-row">
  <div class="meta-chip">📅 {run_ts.strftime('%B %d, %Y %H:%M UTC')}</div>
  <div class="meta-chip">🐍 Python {python_ver}</div>
  <div class="meta-chip">🖥 {platform}</div>
  <div class="meta-chip">🔢 {len(categories)} test categories</div>
  <div class="meta-chip">⚡ pytest + pytest-asyncio</div>
</div>

<div class="cats">
{cat_cards_html}
</div>

<div class="footer">
  PolicyCrab Benchmark Validation Report &nbsp;·&nbsp; 
  Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;·&nbsp;
  For acquisition due diligence purposes only.
</div>

</body>
</html>"""

    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"\n✅ Report generated: {OUTPUT_FILE.resolve()}")
    print(f"   {total} tests | {passed} passed | {failed} failed | {accuracy}% pass rate")
    print(f"   Open in browser: file://{OUTPUT_FILE.resolve()}")

if __name__ == "__main__":
    main()
