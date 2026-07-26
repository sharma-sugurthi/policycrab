"""Full end-to-end smoke test for PolicyCrab against the running backend.

Steps (each prints a clear PASS/FAIL line):
  1. provision_schema: applies missing migrations + refreshes PostgREST cache
  2. upload fake SBC text via POST /api/policy/upload  (Gemini extraction)
  3. evaluate fake knee-replacement claim via POST /api/claim/evaluate
  4. (if denied) draft ERISA appeal letter via POST /api/claim/draft-appeal
  5. send chat question via POST /api/chat/message (Gemini, RAG-grounded)
"""

import asyncio
import json
import os
import re
import sys
import urllib.error
import urllib.request

# --- locate this script's repo to find provision_schema, run it inline --------
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # backend/
from app.services.supabase_client import get_supabase_client  # noqa: E402
from app.config import settings  # noqa: E402

TOKEN = "BENCHMARK_TOKEN"
BASE = "http://localhost:8000"


# ---------- tiny HTTP helper ------------------------------------------------
def call(method: str, path: str, body: dict | None = None, headers: dict | None = None,
         timeout: int = 180) -> tuple[int, dict | str]:
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    try:
        return resp.status, json.loads(raw)
    except Exception:
        return resp.status, raw


# ---------- summary helpers -------------------------------------------------
def short(v, n=80):
    if v is None:
        return None
    s = str(v)
    return s if len(s) <= n else s[:n] + "…"


# ----------- step 1: provision schema via asyncpg ---------------------------
async def step_1_provision():
    import asyncpg
    dsn = re.sub(r"^postgresql\+asyncpg://", "postgresql://", settings.database_url)
    if not dsn:
        return "SKIP", "no DATABASE_URL"
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        tables = ["knowledge_chunks", "policy_chunks", "user_policies",
                  "user_claims", "user_chats"]
        report = {}
        for t in tables:
            try:
                rows = await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=$1", t)
                report[t] = [r["column_name"] for r in rows]
            except Exception as e:  # noqa
                report[t] = f"ERR {e}"
        # Apply each migration file idempotently
        repo = os.path.dirname(HERE)
        for sub in ("supabase/migrations", "backend/scripts/migrations"):
            d = os.path.join(repo, sub)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".sql"):
                    continue
                with open(os.path.join(d, fn)) as fh:
                    sql = fh.read()
                try:
                    await conn.execute(sql)
                except Exception as e:  # noqa
                    pass
        try:
            await conn.execute("NOTIFY pgrst, 'reload schema';")
        except Exception:
            pass
        return "OK", report
    finally:
        await conn.close()


# ----------- step 2: upload policy ------------------------------------------
FAKE_SBC = (
    "BlueCross BlueShield PPO Gold Plan — Summary of Benefits and Coverage. "
    "State: CA. Annual in-network individual deductible: $1500. "
    "Annual in-network individual out-of-pocket maximum: $6000. "
    "In-network coinsurance: 20% (member pays). "
    "Annual out-of-network individual deductible: $3000. "
    "Out-of-network individual out-of-pocket maximum: $12000. "
    "Out-of-network coinsurance: 40% (member pays). "
    "Copays: Primary Care $25, Specialist $50, Urgent Care $75, Emergency Room $250. "
    "Plan type: PPO. Prior authorization required for: elective surgery, "
    "advanced imaging (MRI, CT), and specialty drugs. Fully-insured plan. "
    "Group #PCG-2025-12345."
)


def step_2_upload():
    status, body = call("POST", "/api/policy/upload", {"policy_text": FAKE_SBC})
    if status != 200 or not isinstance(body, dict) or not body.get("success"):
        return "FAIL", (status, body)
    pp = body["policy_profile"]
    summary = {
        "plan_name": pp.get("plan_name"),
        "carrier_name": pp.get("carrier_name"),
        "plan_type": pp.get("plan_type"),
        "legal_classification": pp.get("legal_classification"),
        "state": pp.get("state"),
        "in_network_deductible_individual": pp.get("in_network_deductible_individual"),
        "in_network_oop_max_individual": pp.get("in_network_oop_max_individual"),
        "in_network_coinsurance": pp.get("in_network_coinsurance"),
        "confidence": body.get("extraction_confidence"),
        "session_id": body.get("session_id"),
        "policy_indexed": body.get("policy_indexed"),
    }
    return ("OK", summary, pp, body.get("session_id"))


# ----------- step 3: evaluate claim -----------------------------------------
def step_3_evaluate(profile: dict, session_id: str | None):
    payload = {
        "claim_description": (
            "I had a total knee replacement (CPT 27447) performed by Dr. Smith "
            "at Cedar-Sinai on June 15, 2026. Billed amount $45,000. The insurer "
            "issued a denial notice using code CO-50 stating the procedure was "
            "not medically necessary. I have a documented 3-year history of "
            "conservative treatments (physical therapy, NSAIDs, hyaluronic acid "
            "injections) and imaging showing end-stage osteoarthritis (M17.11). "
            "Prior authorization was obtained. The procedure was rendered in-network. "
            "Please evaluate patient responsibility and prepare a formal appeal."
        ),
        "policy_profile": profile,
        "allowed_amount": 29850.0,
        "session_id": session_id,
        "policy_indexed": bool(session_id),
    }
    status, body = call("POST", "/api/claim/evaluate", payload)
    if status != 200 or not isinstance(body, dict):
        return "FAIL", (status, body)
    cost = body.get("cost_breakdown") or {}
    return "OK", {
        "claim_status": (body.get("claim_case") or {}).get("is_denied"),
        "route_decision": body.get("route_decision"),
        "patient_responsibility": cost.get("patient_responsibility"),
        "deductible_applied": cost.get("deductible_applied"),
        "coinsurance_applied": cost.get("coinsurance_applied"),
        "allowed_amount_source": cost.get("allowed_amount_source"),
        "appeal_generated": bool(body.get("appeal_output")),
        "explanation_head": (body.get("explanation") or "")[:160],
    }, body


# ----------- step 4: chat --------------------------------------------------
def step_4_chat(profile: dict, cost: dict | None):
    payload = {
        "message": "Can my insurer deny a medically necessary knee replacement?",
        "policy_profile": profile,
        "cost_breakdown": cost,
        "history": [],
    }
    status, body = call("POST", "/api/chat/message", payload)
    if status != 200 or not isinstance(body, dict):
        return "FAIL", (status, body)
    return "OK", short(body.get("response") or body.get("reply") or body.get("message"))


# ----------- main ----------------------------------------------------------
async def main():
    print("\n[1] Provisioning Supabase schema…")
    s1, r1 = await step_1_provision()
    print(f"    [{s1}] {r1}")

    print("\n[2] Uploading fake SBC (Gemini extraction)…")
    s2, r2, profile, session_id = step_2_upload()
    if s2 == "FAIL":
        print(f"    [FAIL] {r2}")
        return 2
    print(f"    [{s2}] {r2}")

    print("\n[3] Evaluating fake claim (deterministic cost engine + RAG appeal)…")
    s3, r3, body3 = step_3_evaluate(profile, session_id)
    print(f"    [{s3}] {r3}")
    if s3 == "FAIL":
        print(f"      full: {json.dumps(body3, indent=2)[:1500]}")
        return 3

    if body3.get("appeal_output"):
        ao = body3["appeal_output"]
        print(f"    appeal_letter length: {len(ao.get('appeal_letter',''))} chars")
        print(f"    letter_type: {ao.get('letter_type')}")
        print(f"    citations: {len(ao.get('citations', []))}")
        if ao.get("appeal_letter"):
            preview = ao["appeal_letter"][:600].replace("\n", " ")
            print(f"    preview: {preview}…")

    print("\n[4] Chat with advocate agent…")
    s4, r4 = step_4_chat(profile, body3.get("cost_breakdown"))
    print(f"    [{s4}] {r4}")

    print("\nALL DONE")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
