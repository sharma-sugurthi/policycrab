"""
API keys: pure rules, key lifecycle, the real get_current_user dependency on a
dummy app (flag-off inertness, scopes, revoked/expired/unknown, workspace keys,
metering attribution, rejection audit) and the management routes' gating.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import auth as auth_module
from app.api.auth import get_current_user
from app.api.org_context import get_org_context
from app.config import settings
from app.middleware import usage_metering
from app.middleware.usage_metering import UsageMeteringMiddleware
from app.services import api_keys as key_service
from app.services import audit_trail
from app.services import organizations as org_service
from app.services import usage as usage_service
from app.services.api_keys import (
    ApiKeyError, build_auth_user, create_api_key, generate_api_key, hash_api_key, key_prefix, key_status,
    list_api_keys, looks_like_api_key, required_scope, resolve_api_key, revoke_api_key, touch_last_used,
)
from fake_supabase import FakeClient

OWNER = str(uuid4())
OTHER = str(uuid4())
ORG = str(uuid4())


@pytest.fixture
def store(monkeypatch):
    data = {"api_keys": [], "organizations": [], "org_members": [], "usage_events": [], "audit_events": []}
    for mod in (key_service, org_service, usage_service, audit_trail):
        monkeypatch.setattr(mod, "get_supabase_client", lambda: FakeClient(data))
    key_service.invalidate_cache()
    return data


@pytest.fixture
def keys_on(monkeypatch):
    monkeypatch.setattr(settings, "api_keys_enabled", True)


def _seed_org(store, role="admin"):
    store["organizations"].append({"id": ORG, "name": "Acme", "slug": "acme-1", "owner_id": OWNER, "plan": "team"})
    store["org_members"].append({"id": str(uuid4()), "org_id": ORG, "user_id": OWNER, "email": "o@x.test", "role": role})


# ── Pure ──────────────────────────────────────────────────────────

def test_key_format_helpers():
    live, test = generate_api_key("live"), generate_api_key("test")
    assert live.startswith("pc_live_") and test.startswith("pc_test_") and len(live) > 40
    assert looks_like_api_key(live) and looks_like_api_key(test)
    assert not looks_like_api_key("eyJhbGciOi...") and not looks_like_api_key(None) and not looks_like_api_key("")
    assert len(key_prefix(live)) == 16 and len(hash_api_key(live)) == 64
    assert hash_api_key(live) == hash_api_key(f" {live} ")


@pytest.mark.parametrize("method,template,expected", [
    ("POST", "/api/claim/evaluate", "claims:evaluate"),
    ("POST", "/api/policy/upload-pdf/async", "policies:upload"),       # wildcard prefix
    ("GET", "/api/history/claims", "history:read"),
    ("GET", "/api/orgs/{org_id}/claims", "history:read"),
    ("GET", "/api/tasks/{task_id}", "tasks:read"),
    ("POST", "/api/deadlines/{deadline_id}/breach-letter", "deadlines:write"),
    ("GET", "/api/claim/evaluate", None),                             # method mismatch
    ("POST", "/api/orgs", None),                                      # workspace management: never
    ("POST", "/api/api-keys", None),                                  # key management: never
    ("DELETE", "/api/history/policies/{policy_id}", None),            # deletions need a human
    ("GET", "/api/admin/stats", None),
    ("POST", "/api/chat/message", None),
    ("POST", None, None),
])
def test_required_scope(method, template, expected):
    assert required_scope(method, template) == expected


def test_key_status():
    now = datetime.now(timezone.utc)
    assert key_status({}) == "ok"
    assert key_status({"revoked_at": now.isoformat()}) == "revoked"
    assert key_status({"expires_at": (now - timedelta(seconds=1)).isoformat()}) == "expired"
    assert key_status({"expires_at": (now + timedelta(days=1)).isoformat()}) == "ok"
    assert key_status({"expires_at": "garbage"}) == "ok"


# ── Lifecycle (service) ───────────────────────────────────────────

def test_create_list_and_revoke_personal_key(store):
    row, raw = create_api_key(OWNER, "Owner@X.test", "CI bot", ["history:read", "claims:evaluate", "claims:evaluate"])
    assert raw.startswith("pc_live_") and row["key_prefix"] == raw[:16]
    assert "key_hash" not in row and row["scopes"] == ["claims:evaluate", "history:read"] and row["active"] is True
    assert row["owner_email"] == "owner@x.test" and "org_id" not in row
    assert store["api_keys"][0]["key_hash"] == hash_api_key(raw) and raw not in str(store["api_keys"])

    _, test_raw = create_api_key(OWNER, None, "sandbox", ["eob:parse"], environment="test", expires_in_days=7)
    assert test_raw.startswith("pc_test_") and store["api_keys"][1]["expires_at"]

    listed = list_api_keys(user_id=OWNER)
    assert [k["name"] for k in listed] == ["CI bot", "sandbox"] and all("key_hash" not in k for k in listed)
    assert list_api_keys(user_id=OTHER) == []

    assert revoke_api_key(row["id"], user_id=OTHER) is None            # not the owner
    revoked = revoke_api_key(row["id"], user_id=OWNER)
    assert revoked["revoked_at"] and revoked["active"] is False
    assert resolve_api_key(raw)[0] == "revoked"                         # cache invalidated on revoke
    assert revoke_api_key(row["id"], user_id=OWNER)["active"] is False  # idempotent


def test_create_validation_and_limits(store):
    with pytest.raises(ApiKeyError, match="Unknown scope"):
        create_api_key(OWNER, None, "x", ["admin:everything"])
    with pytest.raises(ApiKeyError, match="environment"):
        create_api_key(OWNER, None, "x", ["eob:parse"], environment="prod")
    for i in range(key_service.MAX_KEYS_PER_OWNER):
        create_api_key(OWNER, None, f"k{i}", ["eob:parse"])
    with pytest.raises(ApiKeyError, match="Limit"):
        create_api_key(OWNER, None, "one too many", ["eob:parse"])
    # org keys have their own pool
    _seed_org(store)
    create_api_key(OWNER, None, "org key", ["eob:parse"], org_id=ORG)


def test_resolve_states_and_cache(store):
    row, raw = create_api_key(OWNER, None, "k", ["eob:parse"])
    assert resolve_api_key(raw)[0] == "ok"
    assert resolve_api_key("pc_live_" + "x" * 43) == ("unknown", None)
    assert resolve_api_key("not-a-key") == ("unknown", None)

    store["api_keys"].clear()                                           # deleted underneath the cache
    assert resolve_api_key(raw)[0] == "ok"                              # still cached
    key_service.invalidate_cache()
    assert resolve_api_key(raw)[0] == "unknown"

    exp_row, exp_raw = create_api_key(OWNER, None, "old", ["eob:parse"], expires_in_days=1)
    store["api_keys"][-1]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    key_service.invalidate_cache()
    assert resolve_api_key(exp_raw)[0] == "expired"


def test_touch_last_used_is_throttled(store):
    row, raw = create_api_key(OWNER, None, "k", ["eob:parse"])
    _, full = resolve_api_key(raw)
    touch_last_used(full)
    first = store["api_keys"][0]["last_used_at"]
    assert first
    touch_last_used(full)
    assert store["api_keys"][0]["last_used_at"] == first                # within 5 minutes → no second write


def test_build_auth_user_shape():
    row = {"id": "k1", "user_id": OWNER, "owner_email": "o@x.test", "name": "n", "key_prefix": "pc_live_abcdefgh",
           "environment": "test", "scopes": ["eob:parse"], "org_id": ORG}
    user = build_auth_user(row, {"role": "admin"})
    assert user["id"] == OWNER and user["auth_method"] == "api_key"
    assert user["api_key"] == {"id": "k1", "name": "n", "prefix": "pc_live_abcdefgh", "environment": "test",
                               "scopes": ["eob:parse"], "org_id": ORG, "role": "admin"}


# ── Real dependency on a dummy app ────────────────────────────────

def _dummy_app():
    app = FastAPI()
    app.add_middleware(UsageMeteringMiddleware)

    @app.post("/api/claim/evaluate")
    async def evaluate(user: dict = Depends(get_current_user), org_ctx: dict | None = Depends(get_org_context)):
        return {"user": user, "org": org_ctx}

    @app.get("/api/history/claims")
    async def history(user: dict = Depends(get_current_user)):
        return {"user": user}

    @app.post("/api/policy/upload-pdf/async")
    async def upload(user: dict = Depends(get_current_user)):
        return {"ok": True}

    @app.post("/api/orgs")
    async def orgs(user: dict = Depends(get_current_user)):
        return {"ok": True}

    return app


def _jwt_only(token):
    if token == "jwt-ok":
        return {"id": OTHER, "email": "jwt@x.test"}
    raise HTTPException(status_code=401, detail="Invalid authentication credentials")


@pytest.fixture
def dummy(store, monkeypatch):
    monkeypatch.setattr(auth_module, "verify_supabase_token", _jwt_only)
    monkeypatch.setattr(usage_metering, "_schedule", lambda fn: fn())
    return TestClient(_dummy_app())


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_flag_off_keys_are_treated_as_ordinary_tokens(dummy, store, monkeypatch):
    monkeypatch.setattr(settings, "api_keys_enabled", False)
    _, raw = create_api_key(OWNER, None, "k", ["claims:evaluate"])
    assert dummy.post("/api/claim/evaluate", headers=_bearer(raw)).status_code == 401     # went to Supabase, failed
    assert dummy.post("/api/claim/evaluate", headers=_bearer("jwt-ok")).status_code == 200


def test_key_auth_scopes_and_states(dummy, store, keys_on):
    _, raw = create_api_key(OWNER, "o@x.test", "k", ["claims:evaluate", "history:read"])

    res = dummy.post("/api/claim/evaluate", headers=_bearer(raw))
    assert res.status_code == 200, res.text
    user = res.json()["user"]
    assert user["id"] == OWNER and user["auth_method"] == "api_key" and user["email"] == "o@x.test"
    assert user["api_key"]["scopes"] == ["claims:evaluate", "history:read"] and user["api_key"]["org_id"] is None
    assert res.json()["org"] is None
    assert dummy.get("/api/history/claims", headers=_bearer(raw)).status_code == 200

    missing = dummy.post("/api/policy/upload-pdf/async", headers=_bearer(raw))
    assert missing.status_code == 403 and "policies:upload" in missing.json()["detail"]
    blocked = dummy.post("/api/orgs", headers=_bearer(raw))
    assert blocked.status_code == 403 and "cannot be called with an API key" in blocked.json()["detail"]

    assert dummy.post("/api/claim/evaluate", headers=_bearer("pc_live_" + "z" * 43)).status_code == 401
    assert dummy.post("/api/claim/evaluate", headers=_bearer("jwt-ok")).status_code == 200      # JWT path intact

    store["api_keys"][0]["revoked_at"] = datetime.now(timezone.utc).isoformat()
    key_service.invalidate_cache()
    revoked = dummy.post("/api/claim/evaluate", headers=_bearer(raw))
    assert revoked.status_code == 401 and "revoked" in revoked.json()["detail"]

    _, test_raw = create_api_key(OWNER, None, "sandbox", ["claims:evaluate"], environment="test")
    assert dummy.post("/api/claim/evaluate", headers=_bearer(test_raw)).status_code == 200


def test_workspace_bound_key_sets_org_context(dummy, store, keys_on, monkeypatch):
    monkeypatch.setattr(settings, "orgs_enabled", True)
    _seed_org(store, role="admin")
    _, raw = create_api_key(OWNER, "o@x.test", "rcm-integration", ["claims:evaluate"], org_id=ORG)

    res = dummy.post("/api/claim/evaluate", headers=_bearer(raw))
    assert res.status_code == 200, res.text
    assert res.json()["org"] == {"org_id": ORG, "role": "admin"} and res.json()["user"]["api_key"]["org_id"] == ORG
    assert dummy.post("/api/claim/evaluate", headers={**_bearer(raw), "X-Org-Id": ORG}).status_code == 200
    mismatch = dummy.post("/api/claim/evaluate", headers={**_bearer(raw), "X-Org-Id": str(uuid4())})
    assert mismatch.status_code == 400

    store["org_members"][0]["role"] = "viewer"                         # demoted → key stops working
    orphan = dummy.post("/api/claim/evaluate", headers=_bearer(raw))
    assert orphan.status_code == 401 and "no longer has access" in orphan.json()["detail"]
    store["org_members"].clear()                                        # removed entirely
    assert dummy.post("/api/claim/evaluate", headers=_bearer(raw)).status_code == 401

    monkeypatch.setattr(settings, "orgs_enabled", False)
    assert dummy.post("/api/claim/evaluate", headers=_bearer(raw)).status_code == 401


def test_key_usage_is_metered_with_key_and_workspace(dummy, store, keys_on, monkeypatch):
    monkeypatch.setattr(settings, "orgs_enabled", True)
    monkeypatch.setattr(settings, "usage_metering_enabled", True)
    _seed_org(store)
    key_row, raw = create_api_key(OWNER, None, "k", ["claims:evaluate"], org_id=ORG)
    assert dummy.post("/api/claim/evaluate", headers=_bearer(raw)).status_code == 200
    (event,) = store["usage_events"]
    assert event["user_id"] == OWNER and event["org_id"] == ORG and event["event_type"] == "claim.evaluate"
    assert event["metadata"]["api_key_id"] == key_row["id"]


def test_rejections_are_audited_without_leaking_the_key(dummy, store, keys_on, monkeypatch):
    monkeypatch.setattr(settings, "audit_trail_enabled", True)
    bogus = "pc_live_" + "q" * 43
    assert dummy.post("/api/claim/evaluate", headers=_bearer(bogus)).status_code == 401
    _, raw = create_api_key(OWNER, None, "k", ["history:read"])
    assert dummy.post("/api/claim/evaluate", headers=_bearer(raw)).status_code == 403
    reasons = [(r["action"], r["reason"], r["resource_id"]) for r in store["audit_events"]]
    assert reasons == [("api_key.rejected", "unknown", bogus[:16]), ("api_key.rejected", "missing_scope", raw[:16])]
    assert bogus not in str(store["audit_events"]) and raw not in str(store["audit_events"])


# ── Management routes on the real app ─────────────────────────────

@pytest.fixture
def client(store, monkeypatch):
    from app.main import app
    from app.security import rate_limit
    current = {"id": OWNER, "email": "o@x.test"}
    app.dependency_overrides[get_current_user] = lambda: current
    rate_limit._buckets.clear()
    try:
        yield SimpleNamespace(http=TestClient(app), user=current)
    finally:
        app.dependency_overrides.clear()


def test_management_routes_require_auth(store):
    from app.main import app
    saved = dict(app.dependency_overrides)          # some older test modules install overrides at import time
    app.dependency_overrides.clear()
    try:
        http = TestClient(app)
        for method, path in (("GET", "/api/api-keys"), ("POST", "/api/api-keys"), ("GET", "/api/api-keys/scopes"),
                             ("GET", f"/api/orgs/{ORG}/api-keys")):
            res = http.request(method, path, json={"name": "x", "scopes": ["eob:parse"]})
            assert res.status_code in (401, 403), (path, res.status_code)
    finally:
        app.dependency_overrides.update(saved)


def test_management_routes_hidden_when_disabled(client, store, monkeypatch):
    monkeypatch.setattr(settings, "api_keys_enabled", False)
    assert client.http.get("/api/api-keys/scopes").json() == {"enabled": False, "scopes": {}}
    assert client.http.get("/api/api-keys").status_code == 404
    assert client.http.post("/api/api-keys", json={"name": "x", "scopes": ["eob:parse"]}).status_code == 404
    assert store["api_keys"] == []


def test_personal_key_management(client, store, keys_on, monkeypatch):
    from app.api import api_key_routes
    audited = []
    monkeypatch.setattr(api_key_routes, "record_audit", lambda action, **kw: audited.append((action, kw)))
    http = client.http

    scopes = http.get("/api/api-keys/scopes").json()
    assert scopes["enabled"] is True and set(scopes["scopes"]) == set(key_service.ALL_SCOPES)

    created = http.post("/api/api-keys",
                        json={"name": "  Zapier  ", "scopes": ["eob:parse", "history:read"], "expires_in_days": 30})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["key"].startswith("pc_live_") and body["api_key"]["name"] == "Zapier"
    assert body["api_key"]["key_prefix"] == body["key"][:16] and body["api_key"]["expires_at"]

    listed = http.get("/api/api-keys").json()
    assert len(listed) == 1 and listed[0]["key_prefix"] == body["key"][:16] and "key" not in listed[0]
    assert body["key"] not in created.text.replace(body["key"], "", 1)        # appears exactly once

    assert http.post("/api/api-keys", json={"name": "x", "scopes": ["admin:all"]}).status_code == 400
    assert http.post("/api/api-keys", json={"name": "x", "scopes": ["eob:parse"], "environment": "prod"}).status_code == 422
    assert http.post("/api/api-keys", json={"name": "x", "scopes": []}).status_code == 422

    kid = body["api_key"]["id"]
    assert http.delete(f"/api/api-keys/{kid}").json() == {"success": True, "revoked_id": kid}
    assert http.get("/api/api-keys").json()[0]["active"] is False
    assert http.delete(f"/api/api-keys/{uuid4()}").status_code == 404
    assert http.delete("/api/api-keys/not-a-uuid").status_code == 404
    assert [a for a, _ in audited] == ["api_key.created", "api_key.revoked"]
    assert audited[0][1]["metadata"]["scopes"] == "eob:parse,history:read"


def test_workspace_key_management_gating(client, store, keys_on, monkeypatch):
    monkeypatch.setattr(settings, "orgs_enabled", True)
    _seed_org(store, role="owner")
    store["org_members"].append({"id": str(uuid4()), "org_id": ORG, "user_id": OTHER, "email": "m@x.test",
                                 "role": "member"})
    http, current = client.http, client.user

    created = http.post(f"/api/orgs/{ORG}/api-keys", json={"name": "EHR bridge", "scopes": ["claims:evaluate"]})
    assert created.status_code == 201, created.text
    assert created.json()["api_key"]["org_id"] == ORG
    assert len(http.get(f"/api/orgs/{ORG}/api-keys").json()) == 1
    assert http.get("/api/api-keys").json() == []                               # org keys are not personal keys
    assert http.get(f"/api/orgs/{uuid4()}/api-keys").status_code == 404

    current.update({"id": OTHER, "email": "m@x.test"})
    assert http.get(f"/api/orgs/{ORG}/api-keys").status_code == 403             # member, not admin
    assert http.post(f"/api/orgs/{ORG}/api-keys", json={"name": "x", "scopes": ["eob:parse"]}).status_code == 403

    current.update({"id": OWNER, "email": "o@x.test"})
    kid = created.json()["api_key"]["id"]
    assert http.delete(f"/api/orgs/{ORG}/api-keys/{kid}").status_code == 200
    # an org key cannot be revoked through the personal route
    assert http.delete(f"/api/api-keys/{kid}").status_code == 404


def test_keys_cannot_manage_keys(client, store, keys_on):
    client.user.update({"auth_method": "api_key", "api_key": {"id": "k", "scopes": ["history:read"], "org_id": None}})
    res = client.http.get("/api/api-keys")
    assert res.status_code == 403 and "cannot manage" in res.json()["detail"]
