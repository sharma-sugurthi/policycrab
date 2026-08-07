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
    <title>PolicyCrab Enterprise Benchmark Report</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        
        :root {
            --bg: #09090b;
            --surface: #18181b;
            --surface-hover: #27272a;
            --text: #f4f4f5;
            --text-muted: #a1a1aa;
            --accent: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.5);
            --success: #10b981;
            --danger: #ef4444;
            --border: #27272a;
        }
        
        body {
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 60px 20px;
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(59, 130, 246, 0.08), transparent 25%),
                radial-gradient(circle at 85% 30%, rgba(16, 185, 129, 0.05), transparent 25%);
            background-attachment: fixed;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 60px;
        }
        
        h1 {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(to right, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .subtitle {
            color: var(--text-muted);
            font-size: 1.25rem;
            font-weight: 300;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 24px;
            margin-bottom: 60px;
        }
        
        .stat-card {
            background-color: var(--surface);
            padding: 30px;
            border-radius: 16px;
            border: 1px solid var(--border);
            text-align: center;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            border-color: rgba(255,255,255,0.1);
        }
        
        .stat-value {
            font-size: 4rem;
            font-weight: 700;
            margin-bottom: 10px;
            line-height: 1;
        }
        
        .accuracy-val { color: var(--accent); text-shadow: 0 0 20px var(--accent-glow); }
        .passed-val { color: var(--success); }
        .failed-val { color: {fail_color}; }
        
        .stat-label {
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 0.875rem;
            font-weight: 600;
            letter-spacing: 0.1em;
        }
        
        .section-title {
            font-size: 1.75rem;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
        }
        
        .table-container {
            background-color: var(--surface);
            border-radius: 16px;
            border: 1px solid var(--border);
            overflow: hidden;
            margin-bottom: 40px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 18px 24px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        
        th {
            background-color: rgba(255,255,255,0.03);
            font-weight: 500;
            color: var(--text-muted);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        tr:last-child td { border-bottom: none; }
        
        tr:hover td { background-color: rgba(255,255,255,0.02); }
        
        .badge {
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            display: inline-block;
            letter-spacing: 0.025em;
        }
        
        .badge-success { background: rgba(16, 185, 129, 0.15); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-danger { background: rgba(239, 68, 68, 0.15); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.3); }
        .badge-warning { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
        .badge-info { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
        .badge-neutral { background: rgba(255,255,255,0.1); color: var(--text); border: 1px solid rgba(255,255,255,0.2); }
        
        .reason-text {
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-top: 6px;
            line-height: 1.4;
        }
        
        .error-type {
            font-weight: 600;
            color: var(--danger);
            margin-bottom: 4px;
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Enterprise Validation Benchmark</h1>
            <div class="subtitle">PolicyCrab Synthetic Reasoning Evaluation Suite</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value accuracy-val">{accuracy}%</div>
                <div class="stat-label">Model Accuracy</div>
            </div>
            <div class="stat-card">
                <div class="stat-value passed-val">{passed}</div>
                <div class="stat-label">Passed Cases</div>
            </div>
            <div class="stat-card">
                <div class="stat-value failed-val">{failed}</div>
                <div class="stat-label">Failed Cases</div>
            </div>
        </div>

        <div class="section-title">
            <span style="color: var(--danger);">●</span> Failed Cases Analysis
        </div>
        <div class="table-container">
            {failed_cases_html}
        </div>

        <div class="section-title" style="margin-top: 60px;">
            <span style="color: var(--success);">●</span> Successfully Validated Cases
        </div>
        <div class="table-container">
            {passed_cases_html}
        </div>
    </div>
</body>
</html>
"""

def determine_error_type(reason):
    reason_lower = reason.lower()
    if "route mismatch" in reason_lower:
        return "Routing Error", "badge-danger"
    elif "contradiction" in reason_lower:
        return "Logic Mismatch", "badge-warning"
    elif "strength" in reason_lower:
        return "Classification Error", "badge-info"
    else:
        return "Evaluation Failure", "badge-danger"

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

    # Generate Failed Cases HTML
    failed_cases_html = ""
    failed_results = [r for r in results if r["status"] == "fail"]
    
    if not failed_results:
        failed_cases_html = '<div style="padding: 40px; text-align: center; color: var(--success); font-weight: 500;">Perfect Score! No failures detected across the suite.</div>'
    else:
        failed_cases_html += "<table><thead><tr><th>Case ID & Category</th><th>Expected Result</th><th>Model Output</th><th>Failure Analysis</th></tr></thead><tbody>"
        for r in failed_results:
            expected_rec = r["expected"].get("appeal_recommendation", r["expected"].get("route_decision", "N/A")).upper()
            actual_rec = r["actual"].get("appeal_recommendation", r["actual"].get("route_decision", "N/A")).upper()
            
            error_title, badge_class = determine_error_type(r['reason'])
            
            failed_cases_html += f"""
            <tr>
                <td>
                    <div style="font-weight: 600; color: var(--text); margin-bottom: 6px;">{r['case_id']}</div>
                    <span class="badge badge-neutral">{r['category']}</span>
                </td>
                <td><span class="badge badge-success">{expected_rec}</span></td>
                <td><span class="badge badge-danger">{actual_rec}</span></td>
                <td>
                    <div class="error-type"><span class="badge {badge_class}">{error_title}</span></div>
                    <div class="reason-text">{r['reason']}</div>
                </td>
            </tr>
            """
        failed_cases_html += "</tbody></table>"

    # Generate Passed Cases HTML
    passed_cases_html = ""
    passed_results = [r for r in results if r["status"] == "pass"]
    
    if not passed_results:
        passed_cases_html = '<div style="padding: 40px; text-align: center; color: var(--text-muted);">No cases passed.</div>'
    else:
        passed_cases_html += "<table><thead><tr><th>Case ID</th><th>Category</th><th>Validated Output</th><th>Status</th></tr></thead><tbody>"
        for r in passed_results:
            expected_rec = r["expected"].get("appeal_recommendation", r["expected"].get("route_decision", "N/A")).upper()
            passed_cases_html += f"""
            <tr>
                <td style="font-weight: 500;">{r['case_id']}</td>
                <td><span class="badge badge-neutral">{r['category']}</span></td>
                <td><span class="badge badge-success">{expected_rec}</span></td>
                <td><span class="badge badge-success">✓ Passed</span></td>
            </tr>
            """
        passed_cases_html += "</tbody></table>"

    final_html = HTML_TEMPLATE.replace("{accuracy}", f"{accuracy:.1f}") \
        .replace("{passed}", str(passed)) \
        .replace("{failed}", str(failed)) \
        .replace("{fail_color}", fail_color) \
        .replace("{failed_cases_html}", failed_cases_html) \
        .replace("{passed_cases_html}", passed_cases_html)

    with open(REPORT_FILE, "w") as f:
        f.write(final_html)
        
    print(f"HTML Report generated at: {REPORT_FILE.absolute()}")

if __name__ == "__main__":
    generate_report()
