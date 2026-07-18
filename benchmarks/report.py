import json
import os
from pathlib import Path

RESULTS_FILE = Path("results.json")
REPORT_FILE = Path("report.html")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PolicyCrab Benchmark Report</title>
    <style>
        :root {
            --bg: #0f111a;
            --surface: #1e2130;
            --text: #e2e8f0;
            --text-muted: #94a3b8;
            --accent: #3b82f6;
            --success: #10b981;
            --danger: #ef4444;
            --border: #334155;
        }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px 20px;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        h1, h2 {
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .stat-card {
            background-color: var(--surface);
            padding: 24px;
            border-radius: 12px;
            border: 1px solid var(--border);
            text-align: center;
        }
        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--accent);
            margin-bottom: 8px;
        }
        .stat-label {
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 0.875rem;
            letter-spacing: 0.05em;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background-color: var(--surface);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        th, td {
            padding: 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        th {
            background-color: rgba(0,0,0,0.2);
            font-weight: 600;
            color: var(--text-muted);
        }
        .badge {
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            display: inline-block;
        }
        .badge-success { background: rgba(16, 185, 129, 0.1); color: var(--success); }
        .badge-danger { background: rgba(239, 68, 68, 0.1); color: var(--danger); }
        .case-fail { border-left: 4px solid var(--danger); }
    </style>
</head>
<body>
    <div class="container">
        <h1>PolicyCrab 10/10 Benchmark Report</h1>
        <p style="color: var(--text-muted); margin-bottom: 40px;">Synthetic Evaluation Suite for Deterministic Reasoning</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{accuracy}%</div>
                <div class="stat-label">Overall Accuracy</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: var(--success);">{passed}</div>
                <div class="stat-label">Passed Cases</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: {fail_color};">{failed}</div>
                <div class="stat-label">Failed Cases</div>
            </div>
        </div>

        <h2>Failed Cases</h2>
        {failed_cases_html}
    </div>
</body>
</html>
"""

def generate_report():
    if not RESULTS_FILE.exists():
        print("results.json not found. Run run_benchmark.py first.")
        return

    with open(RESULTS_FILE, "r") as f:
        data = json.load(f)

    summary = data["summary"]
    results = data["results"]
    
    accuracy = summary["accuracy_percent"]
    passed = summary["passed"]
    failed = summary["total"] - passed
    
    fail_color = "var(--danger)" if failed > 0 else "var(--success)"

    failed_cases_html = ""
    failed_results = [r for r in results if r["status"] == "fail"]
    
    if not failed_results:
        failed_cases_html = '<div class="stat-card" style="border-color: var(--success); color: var(--success);">Perfect Score! No failed cases.</div>'
    else:
        failed_cases_html += "<table><thead><tr><th>Case ID</th><th>Category</th><th>Expected</th><th>Actual</th><th>Reason</th></tr></thead><tbody>"
        for r in failed_results:
            expected_rec = r["expected"].get("appeal_recommendation", "N/A")
            actual_rec = r["actual"].get("appeal_recommendation", "N/A")
            failed_cases_html += f"""
            <tr class="case-fail">
                <td><strong>{r['case_id']}</strong></td>
                <td>{r['category']}</td>
                <td><span class="badge badge-success">{expected_rec}</span></td>
                <td><span class="badge badge-danger">{actual_rec}</span></td>
                <td style="font-size: 0.875rem; color: var(--danger);">{r['reason']}</td>
            </tr>
            """
        failed_cases_html += "</tbody></table>"

    final_html = HTML_TEMPLATE.format(
        accuracy=f"{accuracy:.1f}",
        passed=passed,
        failed=failed,
        fail_color=fail_color,
        failed_cases_html=failed_cases_html
    )

    with open(REPORT_FILE, "w") as f:
        f.write(final_html)
        
    print(f"HTML Report generated at: {REPORT_FILE.absolute()}")

if __name__ == "__main__":
    generate_report()
