"""
Audit trail: recording semantics (hashed IP, sanitised metadata, never raises),
the EASF sink, the business-event hooks over HTTP, and the read API.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.config import settings
from app.models.security import AuditRecord, PolicyDecisionOutcome
from app.security import audit_logger as audit_logger_module
from app.services import audit_trail
from app.services import organizations as org_service
from app.services.audit_trail import hash_ip, record_audit
from fake_supabase import ExplodingClient, FakeClient

USER = str(uuid4())
OTHER = str(uuid4())
ORG = str(uuid4())


@pytest.fixture
def store(monkeypatch):
    data = {"audit_events": [], "organizations": [], "org_members": [], "org_invitations": []}
    monkeypatch.setattr(audit_trail, "get_supabase_client", lambda: FakeClient(data))
    monkeypatch.setattr(org_service, "get_supabase_client", lambda: FakeClient(data))
    return data


@pytest.fixture
def audit_on(monkeypatch):
    monkeypatch.setattr(settings, "audit_trail_enabled", True)


def _request(ip="203.0.113.7", forwarded=None, ua="pytest/1.0"):
    headers = {"user-agent": ua}
    if forwarded:
        headers["x-forwarded-for"] = forwarded
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=ip), scope={}, url=SimpleNamespace(path="/x"))


# ── record_audit ──────────────────────────────────────────────────

def test_record_audit_inert_when_disabled(store, monkeypatch):
    monkeypatch.setattr(settings, "audit_trail_enabled", False)
    assert record_audit("org.created", user_id=USER) is None
    assert store["audit_events"] == []


def test_record_audit_hashes_ip_and_sanitises(store, audit_on):
    row = record_audit(
        "org.invitation.created", user_id=USER, org_id=ORG, resource_type="invitation", resource_id="inv-1",
        metadata={"role": "member", "nested": {"secret": 1}, "email": "x" * 300},
        request=_request(forwarded="198.51.100.9, 10.0.0.1"),
    )
    assert row["ip_hash"] == hash_ip("198.51.100.9") and len(row["ip_hash"]) == 16
    assert "198.51.100.9" not in str(row) and "203.0.113.7" not in str(row)
    assert row["user_agent"] == "pytest/1.0" and row["actor_type"] == "user" and row["outcome"] == "success"
    assert row["metadata"]["role"] == "member" and "nested" not in row["metadata"] and len(row["metadata"]["email"]) == 200
    assert record_audit("x", actor_type="bogus")["actor_type"] == "user"
    assert record_audit("no.request", user_id=USER)["ip_hash"] is None
    assert hash_ip(None) is None


def test_record_audit_swallows_database_errors(monkeypatch, audit_on):
    monkeypatch.setattr(audit_trail, "get_supabase_client", lambda: ExplodingClient())
    assert record_audit("org.created", user_id=USER) is None


def test_easf_decisions_flow_into_the_trail(monkeypatch):
    captured = []
    monkeypatch.setattr(audit_logger_module, "record_audit", lambda action, **kw: captured.append((action, kw)))
    audit_logger_module.audit_logger.log_decision(AuditRecord(
        agent_id="grievance", user_id=USER, requested_action="appeal.generate", resource="claim-1",
        decision=PolicyDecisionOutcome.DENY, policy_reason="RBAC",
    ))
    (action, kw), = captured
    assert action == "easf.decision" and kw["actor_type"] == "agent" and kw["outcome"] == "deny"
    assert kw["user_id"] == USER and kw["resource_id"] == "claim-1" and kw["metadata"]["agent_id"] == "grievance"


# ── Hooks over HTTP ───────────────────────────────────────────────

@pytest.fixture
def client(store, monkeypatch):
    from app.main import app
    from app.security import rate_limit
    current = {"id": USER, "email": "u@x.test"}
    app.dependency_overrides[get_current_user] = lambda: current
    rate_limit._buckets.clear()
    try:
        yield SimpleNamespace(http=TestClient(app), user=current)
    finally:
        app.dependency_overrides.clear()


def _actions(store):
    return [(r["action"], r.get("outcome")) for r in store["audit_events"]]


def test_org_lifecycle_is_audited(client, store, audit_on, monkeypatch):
    from app.api import org_routes
    monkeypatch.setattr(settings, "orgs_enabled", True)
    monkeypatch.setattr(org_routes, "get_email_service", lambda: SimpleNamespace(send_org_invitation=lambda **kw: False))
    http = client.http

    org = http.post("/api/orgs", json={"name": "Acme Advocates"}).json()
    inv = http.post(f"/api/orgs/{org['id']}/invitations", json={"email": "new@x.test", "role": "member"}).json()
    assert http.delete(f"/api/orgs/{org['id']}/invitations/{inv['id']}").status_code == 200
    assert http.patch(f"/api/orgs/{org['id']}", json={"name": "Acme Inc"}).status_code == 200
    assert http.delete(f"/api/orgs/{org['id']}").status_code == 200

    assert _actions(store) == [
        ("org.created", "success"), ("org.invitation.created", "success"), ("org.invitation.revoked", "success"),
        ("org.renamed", "success"), ("org.deleted", "success"),
    ]
    created = store["audit_events"][0]
    assert created["user_id"] == USER and created["org_id"] == org["id"] and created["resource_type"] == "organization"
    assert store["audit_events"][1]["metadata"] == {"role": "member", "email_sent": False}
    assert all(r["ip_hash"] for r in store["audit_events"])          # TestClient supplies a client host


def test_history_deletion_is_audited(client, store, audit_on, monkeypatch):
    from app.api import history_routes
    monkeypatch.setattr(history_routes, "delete_user_policy", lambda uid, pid: True)
    monkeypatch.setattr(history_routes, "delete_user_document", lambda uid, did: False)
    assert client.http.delete("/api/history/policies/pol-1").status_code == 200
    assert client.http.delete("/api/history/documents/doc-1").status_code == 404   # nothing deleted → no audit row
    assert _actions(store) == [("history.policy.deleted", "success")]
    assert store["audit_events"][0]["resource_id"] == "pol-1"


def test_admin_access_is_audited(client, store, audit_on):
    assert client.http.get("/api/admin/stats").status_code == 403
    assert _actions(store) == [("admin.access", "denied")]
    assert store["audit_events"][0]["resource_id"] == "/api/admin/stats" and store["audit_events"][0]["reason"]


def test_outcome_recording_is_audited(client, store, audit_on, monkeypatch):
    from app.api import outcome_routes
    monkeypatch.setattr(outcome_routes, "record_outcome", lambda **kw: {"id": "o1", **kw["payload"]})
    res = client.http.post("/api/outcomes", json={"claim_id": "claim-abc-123", "outcome": "won", "appeal_level": 1})
    assert res.status_code == 201, res.text
    assert _actions(store) == [("outcome.recorded", "success")]
    assert store["audit_events"][0]["metadata"] == {"outcome": "won", "appeal_level": 1}


def test_hooks_are_silent_when_disabled(client, store, monkeypatch):
    monkeypatch.setattr(settings, "audit_trail_enabled", False)
    assert client.http.get("/api/admin/stats").status_code == 403
    assert store["audit_events"] == []


# ── Read API ──────────────────────────────────────────────────────

def test_audit_log_routes_require_auth(store):
    from app.main import app
    http = TestClient(app)
    for path in ("/api/audit-log/me", f"/api/audit-log/org/{ORG}", "/api/admin/audit-log"):
        assert http.get(path).status_code in (401, 403), path


def test_audit_log_routes(client, store, monkeypatch):
    http, current = client.http, client.user
    assert http.get("/api/audit-log/me").json() == {"enabled": False, "events": []}

    monkeypatch.setattr(settings, "audit_trail_enabled", True)
    ts = datetime.now(timezone.utc).isoformat()
    store["org_members"].extend([
        {"id": "m1", "org_id": ORG, "user_id": USER, "email": "u@x.test", "role": "owner"},
        {"id": "m2", "org_id": ORG, "user_id": OTHER, "email": "o@x.test", "role": "viewer"},
    ])
    store["audit_events"].extend([
        {"id": "a1", "user_id": USER, "org_id": ORG, "action": "org.created", "outcome": "success", "created_at": ts},
        {"id": "a2", "user_id": OTHER, "org_id": ORG, "action": "org.invitation.accepted", "outcome": "success",
         "created_at": ts},
        {"id": "a3", "user_id": USER, "org_id": None, "action": "history.policy.deleted", "outcome": "success",
         "created_at": ts},
        {"id": "a4", "user_id": OTHER, "org_id": None, "action": "admin.access", "outcome": "denied", "created_at": ts},
    ])

    mine = http.get("/api/audit-log/me").json()
    assert mine["enabled"] is True and sorted(e["id"] for e in mine["events"]) == ["a1", "a3"]
    org = http.get(f"/api/audit-log/org/{ORG}").json()
    assert sorted(e["id"] for e in org["events"]) == ["a1", "a2"]
    assert http.get(f"/api/audit-log/org/{uuid4()}").status_code == 404
    assert http.get("/api/admin/audit-log").status_code == 403

    current.update({"id": OTHER, "email": "o@x.test"})
    assert http.get(f"/api/audit-log/org/{ORG}").status_code == 403          # viewer
    monkeypatch.setattr(settings, "admin_emails", "o@x.test")
    everything = http.get("/api/admin/audit-log").json()
    ids = {e["id"] for e in everything["events"]}
    assert {"a1", "a2", "a3", "a4"} <= ids
    # The admin gate is itself audited, so the denied/allowed admin.access rows from this test appear too.
    assert any(e["action"] == "admin.access" and e["outcome"] == "denied" for e in everything["events"])
    filtered = http.get("/api/admin/audit-log?action=admin.").json()["events"]
    assert filtered and all(e["action"].startswith("admin.") for e in filtered)
    assert "a4" in {e["id"] for e in filtered}
