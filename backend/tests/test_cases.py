"""
Case management: pure pipeline math, scoping (personal vs workspace), role rules,
PHI scrubbing, status transitions, outcome auto-close and the HTTP surface.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.config import settings
from app.services import cases as case_service
from app.services import organizations as org_service
from app.services.cases import (
    CaseError, CaseNotFound, CasePermissionError, add_comment, can_delete, can_write, close_case_from_outcome,
    compute_pipeline_summary, create_case, default_title, delete_case, get_case, list_cases, list_events, make_scope,
    summarize, update_case,
)
from fake_supabase import ExplodingClient, FakeClient

OWNER, ADMIN, MEMBER, VIEWER, OTHER = (str(uuid4()) for _ in range(5))
ORG = str(uuid4())
C_ORG, C_ORG2, C_PERSONAL, C_OTHER = (str(uuid4()) for _ in range(4))
EMAIL = {OWNER: "owner@acme.test", ADMIN: "admin@acme.test", MEMBER: "member@acme.test", VIEWER: "viewer@acme.test"}
TODAY = date(2026, 9, 16)


def _claim(cid, user_id, org_id=None, deadline="2026-10-01", responsibility=1800.5, decision="denied"):
    return {
        "id": cid, "user_id": user_id, "org_id": org_id, "route_decision": decision,
        "claim_description": "MRI of the lumbar spine denied as not medically necessary. Patient has chronic pain.",
        "cost_breakdown_json": {"total_patient_responsibility": responsibility},
        "appeal_output_json": {"appeal_deadline": deadline, "appeal_recommendation": "STRONG_APPEAL",
                               "success_score_band": "HIGH", "triage_path": "PAYER_ILLEGAL_DENIAL"},
        "created_at": "2026-09-01T10:00:00+00:00",
    }


@pytest.fixture
def store(monkeypatch):
    data = {
        "organizations": [{"id": ORG, "name": "Acme Advocates", "slug": "acme", "owner_id": OWNER}],
        "org_members": [
            {"id": str(uuid4()), "org_id": ORG, "user_id": uid, "email": EMAIL[uid], "role": role}
            for uid, role in ((OWNER, "owner"), (ADMIN, "admin"), (MEMBER, "member"), (VIEWER, "viewer"))
        ],
        "user_claims": [
            _claim(C_ORG, MEMBER, ORG), _claim(C_ORG2, ADMIN, ORG, deadline=None, responsibility=None, decision="approved"),
            _claim(C_PERSONAL, OWNER), _claim(C_OTHER, OTHER),
        ],
        "cases": [], "case_events": [], "appeal_outcomes": [],
    }
    for mod in (case_service, org_service):
        monkeypatch.setattr(mod, "get_supabase_client", lambda: FakeClient(data))
    # Deterministic stand-in for the PHI scrubber
    monkeypatch.setattr(case_service, "scrub_phi", lambda t: (t.replace("555-12-3456", "[SSN]"), int("555-12-3456" in t)))
    return data


@pytest.fixture
def cases_on(monkeypatch):
    monkeypatch.setattr(settings, "cases_enabled", True)


ORG_MEMBER = make_scope(MEMBER, {"org_id": ORG, "role": "member"})
ORG_ADMIN = make_scope(ADMIN, {"org_id": ORG, "role": "admin"})
ORG_VIEWER = make_scope(VIEWER, {"org_id": ORG, "role": "viewer"})
PERSONAL_OWNER = make_scope(OWNER, None)
ACTOR = {"id": MEMBER, "email": EMAIL[MEMBER]}


# ── Pure ──────────────────────────────────────────────────────────

def test_scope_and_role_rules():
    assert make_scope("u", None) == {"user_id": "u", "org_id": None, "role": "owner"}
    assert make_scope("u", {"org_id": ORG, "role": "viewer"})["role"] == "viewer"
    assert can_write(ORG_MEMBER) and can_write(PERSONAL_OWNER) and not can_write(ORG_VIEWER)
    case = {"created_by": MEMBER}
    assert can_delete(ORG_MEMBER, case) and can_delete(ORG_ADMIN, case)
    assert not can_delete(make_scope(VIEWER, {"org_id": ORG, "role": "member"}), case)
    assert not can_delete(make_scope(OTHER, None), case)


def test_default_title_truncates():
    assert default_title({"id": "abcdefgh-1", "claim_description": ""}) == "Claim abcdefgh"
    long = {"claim_description": "word " * 60}
    assert default_title(long).endswith("…") and len(default_title(long)) <= 120


def test_pipeline_summary_math():
    cases = [
        {"status": "new", "priority": "high", "due_date": "2026-09-10", "assignee_id": "a",
         "amount_at_stake": 1000, "claim_id": "c1"},
        {"status": "in_review", "priority": "normal", "due_date": "2026-09-20", "assignee_id": None,
         "amount_at_stake": "250.50", "claim_id": "c2"},
        {"status": "appeal_filed", "priority": "urgent", "due_date": None, "assignee_id": "a",
         "amount_at_stake": None, "claim_id": "c3"},
        {"status": "won", "created_at": "2026-08-01T00:00:00+00:00", "closed_at": "2026-08-11T00:00:00+00:00",
         "claim_id": "c4"},
        {"status": "partial", "created_at": "2026-08-01T00:00:00+00:00", "closed_at": "2026-08-21T00:00:00+00:00",
         "claim_id": "c5"},
        {"status": "lost", "created_at": "2026-08-01T00:00:00+00:00", "closed_at": "bad", "claim_id": "c6"},
        {"status": "withdrawn", "claim_id": "c7"},
    ]
    outcomes = {"c4": {"amount_recovered": 5000}, "c5": {"amount_recovered": "1200.25"}, "c6": {"amount_recovered": None}}
    s = compute_pipeline_summary(cases, outcomes, today=TODAY)
    assert (s["total"], s["open"], s["closed"]) == (7, 3, 4)
    assert s["overdue"] == 1 and s["due_soon"] == 1 and s["unassigned"] == 1
    assert s["amount_at_stake_open"] == 1250.5 and s["amount_recovered"] == 6200.25
    assert s["decided"] == 3 and s["overturn_rate"] == round(2 / 3, 3)
    assert s["avg_days_to_close"] == 15.0
    assert s["open_by_assignee"] == {"a": 2} and s["open_by_priority"]["urgent"] == 1
    empty = compute_pipeline_summary([], {}, TODAY)
    assert empty["overturn_rate"] is None and empty["avg_days_to_close"] is None and empty["total"] == 0


# ── Create / visibility ───────────────────────────────────────────

def test_create_case_defaults_from_claim(store):
    case = create_case(ORG_MEMBER, ACTOR, C_ORG, notes="Call member at 555-12-3456 tomorrow")
    assert case["org_id"] == ORG and case["status"] == "new" and case["created_by"] == MEMBER
    assert case["due_date"] == "2026-10-01" and case["amount_at_stake"] == 1800.5
    assert case["title"].startswith("MRI of the lumbar spine")
    assert case["notes"] == "Call member at [SSN] tomorrow"            # scrubbed before storage
    assert case["claim"]["success_score_band"] == "HIGH" and case["claim"]["route_decision"] == "denied"
    assert case["created_by_email"] == EMAIL[MEMBER] and case["assignee_email"] is None
    assert [e["event_type"] for e in store["case_events"]] == ["created"]

    no_defaults = create_case(ORG_ADMIN, {"id": ADMIN}, C_ORG2, title="Follow-up on approved claim", assignee_id=MEMBER)
    assert no_defaults["due_date"] is None and no_defaults["amount_at_stake"] is None
    assert no_defaults["assignee_email"] == EMAIL[MEMBER]


def test_create_case_rules(store):
    create_case(ORG_MEMBER, ACTOR, C_ORG)
    with pytest.raises(CaseError, match="already exists"):
        create_case(ORG_MEMBER, ACTOR, C_ORG)
    with pytest.raises(CasePermissionError):
        create_case(ORG_VIEWER, {"id": VIEWER}, C_ORG2)
    with pytest.raises(CaseNotFound):                       # personal claim is not visible in the workspace
        create_case(ORG_MEMBER, ACTOR, C_PERSONAL)
    with pytest.raises(CaseNotFound):                       # someone else's personal claim
        create_case(PERSONAL_OWNER, {"id": OWNER}, C_OTHER)
    with pytest.raises(CaseNotFound):
        create_case(ORG_MEMBER, ACTOR, str(uuid4()))
    with pytest.raises(CaseError, match="member of this workspace"):
        create_case(ORG_ADMIN, {"id": ADMIN}, C_ORG2, assignee_id=OTHER)
    with pytest.raises(CaseError, match="member of this workspace"):   # viewers cannot be assignees
        create_case(ORG_ADMIN, {"id": ADMIN}, C_ORG2, assignee_id=VIEWER)
    with pytest.raises(CaseError, match="yourself"):
        create_case(PERSONAL_OWNER, {"id": OWNER}, C_PERSONAL, assignee_id=MEMBER)
    personal = create_case(PERSONAL_OWNER, {"id": OWNER}, C_PERSONAL, assignee_id=OWNER)
    assert "org_id" not in personal or personal["org_id"] is None


def test_list_is_scoped_and_sorted(store):
    a = create_case(ORG_MEMBER, ACTOR, C_ORG)                              # due 2026-10-01
    b = create_case(ORG_ADMIN, {"id": ADMIN}, C_ORG2, due_date=date(2026, 9, 20))
    p = create_case(PERSONAL_OWNER, {"id": OWNER}, C_PERSONAL)
    update_case(ORG_MEMBER, ACTOR, a["id"], {"status": "won"})

    org_rows = list_cases(ORG_VIEWER)                                       # viewers can read
    assert [r["id"] for r in org_rows] == [b["id"], a["id"]]                # open first, then closed
    assert [r["id"] for r in list_cases(ORG_VIEWER, include_closed=False)] == [b["id"]]
    assert [r["id"] for r in list_cases(ORG_VIEWER, status="won")] == [a["id"]]
    assert [r["id"] for r in list_cases(PERSONAL_OWNER)] == [p["id"]]
    assert list_cases(make_scope(OTHER, None)) == []
    with pytest.raises(CaseNotFound):
        get_case(PERSONAL_OWNER, a["id"])                                   # workspace case invisible personally


# ── Update / comments / delete ────────────────────────────────────

def test_update_transitions_and_events(store):
    case = create_case(ORG_MEMBER, ACTOR, C_ORG)
    cid = case["id"]

    won = update_case(ORG_MEMBER, ACTOR, cid, {"status": "won"})
    assert won["status"] == "won" and won["closed_at"] and won["is_open"] is False
    reopened = update_case(ORG_MEMBER, ACTOR, cid, {"status": "in_review"})
    assert reopened["status"] == "in_review" and reopened["closed_at"] is None

    changes = {"assignee_id": MEMBER, "priority": "urgent", "due_date": date(2026, 9, 18), "notes": "SSN 555-12-3456"}
    assigned = update_case(ORG_ADMIN, {"id": ADMIN}, cid, changes)
    assert assigned["assignee_email"] == EMAIL[MEMBER] and assigned["priority"] == "urgent"
    assert assigned["due_date"] == "2026-09-18" and assigned["notes"] == "SSN [SSN]"
    cleared = update_case(ORG_ADMIN, {"id": ADMIN}, cid, {"clear_assignee": True, "clear_due_date": True})
    assert cleared["assignee_id"] is None and cleared["due_date"] is None

    unchanged = update_case(ORG_MEMBER, ACTOR, cid, {"priority": "urgent"})   # no-op
    assert unchanged["priority"] == "urgent"
    types = [e["event_type"] for e in store["case_events"]]
    assert types == ["created", "status_changed", "status_changed", "assigned", "priority_changed", "due_date_changed",
                     "notes_updated", "assigned", "due_date_changed"]
    with pytest.raises(CasePermissionError):
        update_case(ORG_VIEWER, {"id": VIEWER}, cid, {"status": "lost"})
    with pytest.raises(CaseError):
        update_case(ORG_MEMBER, ACTOR, cid, {"assignee_id": OTHER})
    with pytest.raises(CaseNotFound):
        update_case(PERSONAL_OWNER, {"id": OWNER}, cid, {"status": "lost"})


def test_comments_and_delete_rules(store):
    case = create_case(ORG_MEMBER, ACTOR, C_ORG)
    other_case = create_case(ORG_ADMIN, {"id": ADMIN}, C_ORG2)
    event = add_comment(ORG_MEMBER, ACTOR, case["id"], "Spoke to payer, ref 555-12-3456")
    assert event["event_type"] == "comment" and event["message"] == "Spoke to payer, ref [SSN]"
    assert event["actor_email"] == EMAIL[MEMBER]
    with pytest.raises(CasePermissionError):
        add_comment(ORG_VIEWER, {"id": VIEWER}, case["id"], "hi")
    with pytest.raises(CaseError, match="empty"):
        add_comment(ORG_MEMBER, ACTOR, case["id"], "   ")
    assert [e["event_type"] for e in list_events(ORG_VIEWER, case["id"])] == ["comment", "created"]

    with pytest.raises(CasePermissionError):                       # member cannot delete a colleague's case
        delete_case(ORG_MEMBER, other_case["id"])
    assert delete_case(ORG_MEMBER, case["id"]) is True              # ...but can delete their own
    assert delete_case(ORG_ADMIN, other_case["id"]) is True         # admins can delete any
    assert store["cases"] == []


# ── Outcomes & summary ────────────────────────────────────────────

def test_outcome_auto_closes_case(store, cases_on):
    case = create_case(ORG_MEMBER, ACTOR, C_ORG)
    assert close_case_from_outcome(C_ORG, "pending", ACTOR)["status"] == "awaiting_decision"
    closed = close_case_from_outcome(C_ORG, "won", ACTOR)
    assert closed["status"] == "won" and closed["closed_at"]
    assert close_case_from_outcome(C_ORG, "won", ACTOR)["status"] == "won"          # idempotent
    assert close_case_from_outcome(str(uuid4()), "won", ACTOR) is None               # no case
    assert close_case_from_outcome(C_ORG, "maybe", ACTOR) is None                    # unknown outcome
    assert [e["event_type"] for e in store["case_events"]] == ["created", "outcome_recorded", "outcome_recorded"]
    assert get_case(ORG_MEMBER, case["id"])["status"] == "won"


def test_outcome_hook_is_inert_and_never_raises(store, monkeypatch):
    monkeypatch.setattr(settings, "cases_enabled", False)
    assert close_case_from_outcome(C_ORG, "won", ACTOR) is None
    monkeypatch.setattr(settings, "cases_enabled", True)
    monkeypatch.setattr(case_service, "get_supabase_client", lambda: ExplodingClient())
    assert close_case_from_outcome(C_ORG, "won", ACTOR) is None


def test_summarize_uses_outcomes_and_member_emails(store):
    a = create_case(ORG_MEMBER, ACTOR, C_ORG, assignee_id=MEMBER)
    create_case(ORG_ADMIN, {"id": ADMIN}, C_ORG2, due_date=TODAY - timedelta(days=2))
    update_case(ORG_MEMBER, ACTOR, a["id"], {"status": "won"})
    store["appeal_outcomes"].append({"claim_id": C_ORG, "outcome": "won", "amount_recovered": 1500})
    s = summarize(ORG_VIEWER, today=TODAY)
    assert s["total"] == 2 and s["open"] == 1 and s["closed"] == 1 and s["overdue"] == 1
    assert s["amount_recovered"] == 1500.0 and s["overturn_rate"] == 1.0
    assert s["open_by_assignee"] == {} and s["scope"] == {"type": "org", "id": ORG}
    assert summarize(PERSONAL_OWNER, today=TODAY)["total"] == 0


# ── HTTP ──────────────────────────────────────────────────────────

@pytest.fixture
def client(store, monkeypatch):
    from app.main import app
    from app.security import rate_limit
    monkeypatch.setattr(settings, "orgs_enabled", True)
    current = {"id": MEMBER, "email": EMAIL[MEMBER]}
    app.dependency_overrides[get_current_user] = lambda: current
    rate_limit._buckets.clear()
    try:
        yield SimpleNamespace(http=TestClient(app), user=current)
    finally:
        app.dependency_overrides.clear()


def test_features_and_flag_off(client, monkeypatch):
    monkeypatch.setattr(settings, "cases_enabled", False)
    feats = client.http.get("/api/features").json()
    assert feats["cases"] is False and feats["orgs"] is True
    assert set(feats) == {"orgs", "api_keys", "cases", "usage_metering", "audit_trail"}
    assert client.http.get("/api/cases").status_code == 404
    assert client.http.post("/api/cases", json={"claim_id": C_ORG}).status_code == 404


def test_case_flow_over_http(client, store, cases_on):
    http, current = client.http, client.user
    org = {"X-Org-Id": ORG}

    created = http.post("/api/cases", json={"claim_id": C_ORG, "priority": "high"}, headers=org)
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["org_id"] == ORG and case["priority"] == "high"
    assert case["claim"]["appeal_recommendation"] == "STRONG_APPEAL"
    assert http.post("/api/cases", json={"claim_id": C_ORG}, headers=org).status_code == 400   # duplicate
    bad_priority = {"claim_id": C_ORG2, "priority": "asap"}
    assert http.post("/api/cases", json=bad_priority, headers=org).status_code == 422

    listed = http.get("/api/cases", headers=org).json()
    assert listed["scope"] == {"type": "org", "id": ORG, "role": "member"}
    assert [c["id"] for c in listed["cases"]] == [case["id"]]
    assert http.get("/api/cases").json()["cases"] == []                       # personal scope: nothing
    assert http.get(f"/api/cases/{case['id']}").status_code == 404             # invisible without the workspace
    assert http.get("/api/cases/not-a-uuid", headers=org).status_code == 404

    patched = http.patch(f"/api/cases/{case['id']}", json={"status": "appeal_filed", "assignee_id": MEMBER}, headers=org)
    assert patched.status_code == 200 and patched.json()["status"] == "appeal_filed"
    assert patched.json()["assignee_email"] == EMAIL[MEMBER]
    assert http.patch(f"/api/cases/{case['id']}", json={"status": "flying"}, headers=org).status_code == 422
    assert http.post(f"/api/cases/{case['id']}/comments", json={"message": "Filed by fax."}, headers=org).status_code == 201
    events = http.get(f"/api/cases/{case['id']}/events", headers=org).json()["events"]
    assert [e["event_type"] for e in events] == ["comment", "assigned", "status_changed", "created"]
    assert http.get("/api/cases?assignee_id=me", headers=org).json()["cases"][0]["id"] == case["id"]

    summary = http.get("/api/cases/summary", headers=org).json()
    assert summary["open"] == 1 and summary["by_status"]["appeal_filed"] == 1

    current.update({"id": VIEWER, "email": EMAIL[VIEWER]})
    assert http.get("/api/cases", headers=org).status_code == 200
    assert http.post("/api/cases", json={"claim_id": C_ORG2}, headers=org).status_code == 403
    assert http.patch(f"/api/cases/{case['id']}", json={"status": "won"}, headers=org).status_code == 403
    assert http.delete(f"/api/cases/{case['id']}", headers=org).status_code == 403

    current.update({"id": OTHER, "email": "outsider@x.test"})
    assert http.get("/api/cases", headers=org).status_code == 404                                       # not a member

    current.update({"id": MEMBER, "email": EMAIL[MEMBER]})
    assert http.delete(f"/api/cases/{case['id']}", headers=org).json()["success"] is True
    assert http.get("/api/cases", headers=org).json()["cases"] == []
