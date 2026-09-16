"""
Usage metering: pure aggregation, route→event mapping, the middleware on a dummy
app wired with the REAL get_current_user dependency, workspace attribution, and
the read API. Supabase is an in-memory fake (tests/fake_supabase.py).
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import auth as auth_module
from app.api.auth import get_current_user
from app.api.org_context import get_org_context
from app.config import settings
from app.middleware import usage_metering
from app.middleware.usage_metering import UsageMeteringMiddleware, resolve_event_type
from app.services import organizations as org_service
from app.services import usage as usage_service
from app.services.usage import aggregate_usage, clean_metadata, record_usage
from fake_supabase import ExplodingClient, FakeClient

USER = str(uuid4())
OTHER = str(uuid4())
ORG = str(uuid4())
NOW = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(monkeypatch):
    data = {"usage_events": [], "org_members": [], "organizations": []}
    monkeypatch.setattr(usage_service, "get_supabase_client", lambda: FakeClient(data))
    monkeypatch.setattr(org_service, "get_supabase_client", lambda: FakeClient(data))
    return data


@pytest.fixture
def metering_on(monkeypatch):
    monkeypatch.setattr(settings, "usage_metering_enabled", True)


@pytest.fixture
def sync_schedule(monkeypatch):
    monkeypatch.setattr(usage_metering, "_schedule", lambda fn: fn())


# ── Pure ──────────────────────────────────────────────────────────

def test_clean_metadata_keeps_only_small_scalars():
    meta = {"status": 200, "async": False, "nested": {"phi": "x"}, "list": [1], "note": "a" * 500, 3: "bad"}
    out = clean_metadata(meta)
    assert out["status"] == 200 and out["async"] is False
    assert "nested" not in out and "list" not in out and 3 not in out
    assert len(out["note"]) == 200
    assert clean_metadata(None) == {} and clean_metadata("nope") == {}


def test_aggregate_usage_totals_by_type_and_day():
    rows = [
        {"event_type": "claim.evaluate", "quantity": 1, "created_at": "2026-09-13T10:00:00+00:00"},
        {"event_type": "claim.evaluate", "quantity": 2, "created_at": "2026-09-13T23:59:00Z"},
        {"event_type": "policy.upload", "quantity": 1, "created_at": "2026-09-12T09:00:00+00:00"},
        {"event_type": None, "quantity": None, "created_at": "not-a-date"},
    ]
    out = aggregate_usage(rows, days=7, until=NOW)
    assert out["total"] == 5
    assert out["by_type"] == {"claim.evaluate": 3, "policy.upload": 1, "unknown": 1}
    assert out["by_day"] == [{"date": "2026-09-12", "count": 1}, {"date": "2026-09-13", "count": 3}]
    assert out["since"] == (NOW - timedelta(days=7)).isoformat() and out["days"] == 7
    assert aggregate_usage([], 30, NOW)["total"] == 0


@pytest.mark.parametrize("method,template,raw,expected", [
    ("POST", "/api/claim/evaluate", "/api/claim/evaluate", "claim.evaluate"),
    ("POST", "/api/claim/evaluate/async", "/api/claim/evaluate/async", "claim.evaluate"),
    ("POST", "/api/deadlines/{deadline_id}/breach-letter", "/api/deadlines/abc/breach-letter", "deadline.breach_letter"),
    ("POST", None, "/api/deadlines/abc/breach-letter", "deadline.breach_letter"),   # no route object → regex fallback
    ("POST", None, "/studio/dossier", "dossier.compile"),
    ("GET", "/api/claim/evaluate", "/api/claim/evaluate", None),                     # wrong method
    ("POST", "/api/orgs", "/api/orgs", None),                                        # not billable
    ("POST", "/api/history/claims", "/api/history/claims", None),
])
def test_resolve_event_type(method, template, raw, expected):
    event, _ = resolve_event_type(method, template, raw)
    assert event == expected


# ── record_usage ──────────────────────────────────────────────────

def test_record_usage_inert_when_disabled(store, monkeypatch):
    monkeypatch.setattr(settings, "usage_metering_enabled", False)
    assert record_usage(USER, "claim.evaluate") is None
    assert store["usage_events"] == []


def test_record_usage_inserts_and_omits_org_when_none(store, metering_on):
    personal = record_usage(USER, "claim.evaluate", route="/api/claim/evaluate", metadata={"status": 200, "x": {"y": 1}})
    assert personal["user_id"] == USER and "org_id" not in personal
    assert personal["metadata"] == {"status": 200} and personal["quantity"] == 1
    scoped = record_usage(USER, "policy.upload", org_id=ORG, quantity=0)
    assert scoped["org_id"] == ORG and scoped["quantity"] == 1
    assert len(store["usage_events"]) == 2
    assert record_usage(None, "claim.evaluate") is None and record_usage(USER, "") is None


def test_record_usage_swallows_database_errors(monkeypatch, metering_on):
    monkeypatch.setattr(usage_service, "get_supabase_client", lambda: ExplodingClient())
    assert record_usage(USER, "claim.evaluate") is None


# ── Middleware on a dummy app using the REAL auth dependency ──────

def _dummy_app():
    app = FastAPI()
    app.add_middleware(UsageMeteringMiddleware)

    @app.post("/api/claim/evaluate")
    async def evaluate(user: dict = Depends(get_current_user), org_ctx: dict | None = Depends(get_org_context)):
        return {"ok": True, "org": org_ctx}

    @app.post("/api/deadlines/{deadline_id}/breach-letter")
    async def breach(deadline_id: str, user: dict = Depends(get_current_user)):
        return {"ok": deadline_id}

    @app.post("/api/claim/draft-appeal")
    async def draft(user: dict = Depends(get_current_user)):
        raise HTTPException(status_code=400, detail="bad request")

    @app.post("/api/eob/parse")
    async def anonymous_parse():
        return {"ok": True}          # no auth dependency → no identity → nothing to bill

    @app.get("/api/history/claims")
    async def history(user: dict = Depends(get_current_user)):
        return []

    return app


@pytest.fixture
def dummy(store, monkeypatch, sync_schedule):
    monkeypatch.setattr(auth_module, "verify_supabase_token", lambda token: {"id": USER, "email": "u@x.test"})
    return TestClient(_dummy_app())


AUTH = {"Authorization": "Bearer test-token"}


def test_middleware_records_billable_success_only(dummy, store, metering_on):
    assert dummy.post("/api/claim/evaluate", headers=AUTH).status_code == 200
    assert dummy.post("/api/deadlines/abc-123/breach-letter", headers=AUTH).status_code == 200
    assert dummy.post("/api/claim/draft-appeal", headers=AUTH).status_code == 400   # failure → not billed
    assert dummy.get("/api/history/claims", headers=AUTH).status_code == 200         # not billable
    assert dummy.post("/api/eob/parse").status_code == 200                           # no identity
    assert dummy.post("/api/claim/evaluate").status_code in (401, 403)               # unauthenticated

    rows = store["usage_events"]
    assert [(r["event_type"], r["route"]) for r in rows] == [
        ("claim.evaluate", "/api/claim/evaluate"),
        ("deadline.breach_letter", "/api/deadlines/{deadline_id}/breach-letter"),
    ]
    assert all(r["user_id"] == USER and "org_id" not in r for r in rows)
    assert rows[0]["metadata"] == {"status": 200, "async": False}


def test_middleware_inert_when_disabled(dummy, store, monkeypatch):
    monkeypatch.setattr(settings, "usage_metering_enabled", False)
    assert dummy.post("/api/claim/evaluate", headers=AUTH).status_code == 200
    assert store["usage_events"] == []


def test_middleware_workspace_attribution(dummy, store, metering_on, monkeypatch):
    monkeypatch.setattr(settings, "orgs_enabled", True)
    store["org_members"].append({"id": "m1", "org_id": ORG, "user_id": USER, "email": "u@x.test", "role": "member"})

    # Verified via get_org_context on the route → attributed
    assert dummy.post("/api/claim/evaluate", headers={**AUTH, "X-Org-Id": ORG}).status_code == 200
    assert store["usage_events"][-1]["org_id"] == ORG

    # Header names an org the user does not belong to → route rejects (404) → nothing billed
    stranger_org = str(uuid4())
    n_before = len(store["usage_events"])
    assert dummy.post("/api/claim/evaluate", headers={**AUTH, "X-Org-Id": stranger_org}).status_code == 404
    assert len(store["usage_events"]) == n_before

    # Route without get_org_context: bare header is only honoured after a membership check
    assert dummy.post("/api/deadlines/d1/breach-letter", headers={**AUTH, "X-Org-Id": ORG}).status_code == 200
    assert store["usage_events"][-1]["org_id"] == ORG
    assert dummy.post("/api/deadlines/d1/breach-letter", headers={**AUTH, "X-Org-Id": stranger_org}).status_code == 200
    assert "org_id" not in store["usage_events"][-1]

    # Feature disabled → header ignored, personal
    monkeypatch.setattr(settings, "orgs_enabled", False)
    assert dummy.post("/api/deadlines/d1/breach-letter", headers={**AUTH, "X-Org-Id": ORG}).status_code == 200
    assert "org_id" not in store["usage_events"][-1]


# ── Read API on the real app ──────────────────────────────────────

@pytest.fixture
def client(store, monkeypatch):
    from app.main import app
    current = {"id": USER, "email": "u@x.test"}
    app.dependency_overrides[get_current_user] = lambda: current
    try:
        yield TestClient(app), current
    finally:
        app.dependency_overrides.clear()


def test_usage_routes_require_auth(store):
    from app.main import app
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        http = TestClient(app)
        for path in ("/api/usage/me", f"/api/usage/org/{ORG}", "/api/admin/usage"):
            assert http.get(path).status_code in (401, 403), path
    finally:
        app.dependency_overrides.update(saved)


def test_usage_routes_report_disabled(client):
    http, _ = client
    body = http.get("/api/usage/me").json()
    assert body["enabled"] is False and body["total"] == 0
    assert http.get("/api/admin/usage").status_code == 403       # not an admin


def test_usage_routes_summaries_and_gating(client, store, metering_on, monkeypatch):
    http, current = client
    store["org_members"].extend([
        {"id": "m1", "org_id": ORG, "user_id": USER, "email": "u@x.test", "role": "admin"},
        {"id": "m2", "org_id": ORG, "user_id": OTHER, "email": "o@x.test", "role": "member"},
    ])
    ts = datetime.now(timezone.utc).isoformat()
    store["usage_events"].extend([
        {"id": "e1", "user_id": USER, "org_id": ORG, "event_type": "claim.evaluate", "quantity": 1, "created_at": ts},
        {"id": "e2", "user_id": OTHER, "org_id": ORG, "event_type": "claim.evaluate", "quantity": 1, "created_at": ts},
        {"id": "e3", "user_id": USER, "org_id": None, "event_type": "policy.upload", "quantity": 1, "created_at": ts},
        {"id": "e4", "user_id": USER, "org_id": None, "event_type": "chat.message", "quantity": 1,
         "created_at": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()},   # outside the window
    ])

    mine = http.get("/api/usage/me?days=30").json()
    assert mine["enabled"] is True and mine["total"] == 2
    assert mine["by_type"] == {"claim.evaluate": 1, "policy.upload": 1}

    org = http.get(f"/api/usage/org/{ORG}").json()
    assert org["total"] == 2 and org["by_user"] == {USER: 1, OTHER: 1}
    assert http.get(f"/api/usage/org/{uuid4()}").status_code == 404
    assert http.get("/api/usage/org/not-a-uuid").status_code == 404

    current.update({"id": OTHER, "email": "o@x.test"})
    assert http.get(f"/api/usage/org/{ORG}").status_code == 403           # member, not admin

    monkeypatch.setattr(settings, "admin_emails", "o@x.test")
    platform = http.get("/api/admin/usage?group=org").json()
    assert platform["enabled"] is True and platform["total"] == 3
    assert [g["key"] for g in platform["groups"]] == [ORG, "personal"]
    assert http.get("/api/admin/usage?group=bogus").status_code == 422
