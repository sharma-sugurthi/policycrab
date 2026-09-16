"""
Organizations (team workspaces): role rules, invitations, membership resolution
and the HTTP surface. Supabase is replaced by an in-memory fake (pattern from
test_outcomes.py) so every rule is exercised without a database.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.config import settings
from app.services import organizations as org_service
from app.services import user_data
from app.services.organizations import (
    OrgError,
    OrgNotFound,
    OrgPermissionError,
    accept_invitation,
    can_grant_role,
    can_manage_member,
    create_invitation,
    create_organization,
    hash_invitation_token,
    invitation_status,
    list_org_claims,
    list_user_organizations,
    remove_member,
    require_membership,
    resolve_org_context,
    role_at_least,
    slugify,
    update_member_role,
)

OWNER, ADMIN, MEMBER, VIEWER, OUTSIDER = (str(uuid4()) for _ in range(5))
EMAIL = {
    OWNER: "owner@acme.test", ADMIN: "admin@acme.test", MEMBER: "member@acme.test",
    VIEWER: "viewer@acme.test", OUTSIDER: "outsider@else.test",
}


# ── Fake Supabase client ──────────────────────────────────────────

class _FakeQuery:
    def __init__(self, table, store):
        self.table, self.store = table, store
        self.filters, self.mode, self.payload, self.count_mode = [], "select", None, None

    def select(self, *cols, count=None):
        self.mode, self.count_mode = "select", count
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, list(vals)))
        return self

    def is_(self, col, val):
        self.filters.append(("is", col, val))
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a):
        return self

    def insert(self, payload):
        self.mode, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.mode, self.payload = "update", payload
        return self

    def delete(self):
        self.mode = "delete"
        return self

    def _match(self, row):
        for op, col, val in self.filters:
            rv = row.get(col)
            if op == "eq" and str(rv) != str(val):
                return False
            if op == "in" and str(rv) not in {str(v) for v in val}:
                return False
            if op == "is" and val == "null" and rv is not None:
                return False
        return True

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self.mode == "select":
            out = [dict(r) for r in rows if self._match(r)]
            return SimpleNamespace(data=out, count=len(out) if self.count_mode else None)
        if self.mode == "insert":
            row = dict(self.payload)
            row.setdefault("id", str(uuid4()))
            row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            rows.append(row)
            return SimpleNamespace(data=[dict(row)])
        if self.mode == "update":
            out = []
            for r in rows:
                if self._match(r):
                    r.update(self.payload)
                    out.append(dict(r))
            return SimpleNamespace(data=out)
        out = [dict(r) for r in rows if self._match(r)]
        rows[:] = [r for r in rows if not self._match(r)]
        return SimpleNamespace(data=out)


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeQuery(name, self.store)


@pytest.fixture
def store(monkeypatch):
    data = {"organizations": [], "org_members": [], "org_invitations": [], "user_claims": [], "user_policies": []}
    monkeypatch.setattr(org_service, "get_supabase_client", lambda: _FakeClient(data))
    monkeypatch.setattr(user_data, "get_supabase_client", lambda: _FakeClient(data))
    return data


@pytest.fixture
def orgs_on(monkeypatch):
    monkeypatch.setattr(settings, "orgs_enabled", True)


def _seed_org(store) -> dict:
    """Owner-created org with an admin, a member and a viewer already inside."""
    org = create_organization(OWNER, EMAIL[OWNER], "Acme Advocates")
    for uid, role in ((ADMIN, "admin"), (MEMBER, "member"), (VIEWER, "viewer")):
        store["org_members"].append({"id": str(uuid4()), "org_id": org["id"], "user_id": uid,
                                     "email": EMAIL[uid], "role": role, "created_at": "2026-09-01T00:00:00+00:00"})
    return org


def _actor(org_id, uid):
    return org_service.get_membership(org_id, uid)


# ── Pure rules ────────────────────────────────────────────────────

def test_slugify_and_token_hash():
    slug = slugify("Acme  Advocates, LLC!")
    assert slug.startswith("acme-advocates-llc-") and len(slug.split("-")[-1]) == 6
    assert hash_invitation_token(" abc ") == hash_invitation_token("abc")
    assert len(hash_invitation_token("abc")) == 64


def test_role_ladder():
    assert role_at_least("owner", "admin") and role_at_least("admin", "admin")
    assert not role_at_least("member", "admin") and not role_at_least(None, "viewer")


@pytest.mark.parametrize("actor,target,expected", [
    ("owner", "admin", True), ("owner", "member", True), ("owner", "viewer", True), ("owner", "owner", False),
    ("admin", "admin", False), ("admin", "member", True), ("admin", "viewer", True),
    ("member", "viewer", False), ("viewer", "viewer", False), (None, "member", False),
])
def test_can_grant_role(actor, target, expected):
    assert can_grant_role(actor, target) is expected


@pytest.mark.parametrize("actor,target,expected", [
    ("owner", "admin", True), ("owner", "member", True), ("owner", "owner", False),
    ("admin", "admin", False), ("admin", "member", True), ("admin", "viewer", True), ("admin", "owner", False),
    ("member", "viewer", False), ("viewer", "member", False),
])
def test_can_manage_member(actor, target, expected):
    assert can_manage_member(actor, target) is expected


def test_invitation_status_transitions():
    now = datetime.now(timezone.utc)
    future, past = (now + timedelta(days=1)).isoformat(), (now - timedelta(days=1)).isoformat()
    assert invitation_status({"expires_at": future}, now) == "valid"
    assert invitation_status({"expires_at": past}, now) == "expired"
    assert invitation_status({"expires_at": future, "revoked_at": now.isoformat()}, now) == "revoked"
    assert invitation_status({"expires_at": past, "accepted_at": now.isoformat()}, now) == "accepted"
    assert invitation_status({"expires_at": "garbage"}, now) == "expired"
    assert invitation_status({}, now) == "expired"


# ── Organizations & membership ────────────────────────────────────

def test_create_organization_makes_creator_owner(store):
    org = create_organization(OWNER, EMAIL[OWNER], "Acme Advocates")
    assert org["role"] == "owner" and org["owner_id"] == OWNER
    members = store["org_members"]
    assert len(members) == 1 and members[0]["role"] == "owner" and members[0]["email"] == EMAIL[OWNER]
    mine = list_user_organizations(OWNER)
    assert [o["id"] for o in mine] == [org["id"]] and mine[0]["role"] == "owner"
    assert list_user_organizations(OUTSIDER) == []


def test_owned_org_limit(store):
    for i in range(org_service.MAX_ORGS_OWNED_PER_USER):
        create_organization(OWNER, EMAIL[OWNER], f"Org {i}")
    with pytest.raises(OrgError, match="maximum"):
        create_organization(OWNER, EMAIL[OWNER], "One too many")


def test_require_membership_hides_org_from_non_members(store):
    org = _seed_org(store)
    with pytest.raises(OrgNotFound):
        require_membership(org["id"], OUTSIDER)
    with pytest.raises(OrgPermissionError):
        require_membership(org["id"], VIEWER, minimum="admin")
    assert require_membership(org["id"], ADMIN, minimum="admin")["role"] == "admin"


def test_update_member_role_rules(store):
    org = _seed_org(store)
    oid = org["id"]
    with pytest.raises(OrgPermissionError):        # admin may not mint admins
        update_member_role(oid, _actor(oid, ADMIN), MEMBER, "admin")
    with pytest.raises(OrgPermissionError):        # admin may not touch the owner
        update_member_role(oid, _actor(oid, ADMIN), OWNER, "viewer")
    with pytest.raises(OrgError):                  # nobody edits their own role
        update_member_role(oid, _actor(oid, OWNER), OWNER, "admin")
    with pytest.raises(OrgNotFound):
        update_member_role(oid, _actor(oid, OWNER), OUTSIDER, "member")
    assert update_member_role(oid, _actor(oid, ADMIN), VIEWER, "member")["role"] == "member"
    assert update_member_role(oid, _actor(oid, OWNER), MEMBER, "admin")["role"] == "admin"


def test_remove_member_rules(store):
    org = _seed_org(store)
    oid = org["id"]
    with pytest.raises(OrgError, match="owner"):
        remove_member(oid, _actor(oid, ADMIN), OWNER)
    with pytest.raises(OrgPermissionError):
        remove_member(oid, _actor(oid, VIEWER), MEMBER)
    assert remove_member(oid, _actor(oid, VIEWER), VIEWER) is True       # anyone may leave
    assert remove_member(oid, _actor(oid, ADMIN), MEMBER) is True
    assert {m["user_id"] for m in store["org_members"]} == {OWNER, ADMIN}


# ── Invitations ───────────────────────────────────────────────────

def test_invitation_stores_only_hash_and_revokes_duplicates(store):
    org = _seed_org(store)
    row, raw = create_invitation(org["id"], _actor(org["id"], ADMIN), "New.Person@Example.com", "member")
    assert row["email"] == "new.person@example.com"
    assert row["token_hash"] == hash_invitation_token(raw) and raw not in str(store["org_invitations"])
    row2, _ = create_invitation(org["id"], _actor(org["id"], ADMIN), "new.person@example.com", "viewer")
    pending = org_service.list_pending_invitations(org["id"])
    assert [p["id"] for p in pending] == [row2["id"]]                  # first one revoked
    assert next(r for r in store["org_invitations"] if r["id"] == row["id"])["revoked_at"]


def test_invitation_permission_rules(store):
    org = _seed_org(store)
    oid = org["id"]
    with pytest.raises(OrgPermissionError):
        create_invitation(oid, _actor(oid, MEMBER), "x@y.test", "member")
    with pytest.raises(OrgPermissionError):        # admin cannot invite an admin
        create_invitation(oid, _actor(oid, ADMIN), "x@y.test", "admin")
    with pytest.raises(OrgError, match="already a member"):
        create_invitation(oid, _actor(oid, OWNER), EMAIL[VIEWER], "member")
    with pytest.raises(OrgError, match="already a member"):
        create_invitation(oid, _actor(oid, OWNER), EMAIL[OWNER], "member")
    row, _ = create_invitation(oid, _actor(oid, OWNER), "x@y.test", "admin")
    assert row["role"] == "admin"


def test_accept_invitation_requires_matching_email(store):
    org = _seed_org(store)
    _, raw = create_invitation(org["id"], _actor(org["id"], OWNER), EMAIL[OUTSIDER], "member")
    with pytest.raises(OrgPermissionError, match="different email"):
        accept_invitation(str(uuid4()), "someone.else@x.test", raw)
    with pytest.raises(OrgPermissionError):
        accept_invitation(str(uuid4()), None, raw)
    membership = accept_invitation(OUTSIDER, EMAIL[OUTSIDER].upper(), raw)
    assert membership["role"] == "member" and membership["email"] == EMAIL[OUTSIDER]
    assert store["org_invitations"][0]["accepted_at"]
    # Second redemption by the same (now) member is idempotent
    assert accept_invitation(OUTSIDER, EMAIL[OUTSIDER], raw)["user_id"] == OUTSIDER
    # ...but a different user cannot reuse the token
    with pytest.raises(OrgError, match="already been used"):
        accept_invitation(str(uuid4()), EMAIL[OUTSIDER], raw)


def test_accept_invitation_rejects_expired_revoked_unknown(store):
    org = _seed_org(store)
    oid = org["id"]
    _, expired_raw = create_invitation(oid, _actor(oid, OWNER), "late@x.test", "member")
    store["org_invitations"][-1]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with pytest.raises(OrgError, match="expired"):
        accept_invitation(str(uuid4()), "late@x.test", expired_raw)

    row, revoked_raw = create_invitation(oid, _actor(oid, OWNER), "gone@x.test", "member")
    assert org_service.revoke_invitation(oid, _actor(oid, ADMIN), row["id"]) is True
    with pytest.raises(OrgError, match="revoked"):
        accept_invitation(str(uuid4()), "gone@x.test", revoked_raw)

    with pytest.raises(OrgNotFound):
        accept_invitation(str(uuid4()), "who@x.test", "not-a-real-token-at-all")
    assert org_service.preview_invitation("nope")["status"] == "invalid"
    preview = org_service.preview_invitation(revoked_raw)
    assert preview["status"] == "revoked" and preview["org_name"] == "Acme Advocates"


# ── Request context & workspace data ──────────────────────────────

def test_resolve_org_context_is_inert_when_disabled(store, monkeypatch):
    org = _seed_org(store)
    monkeypatch.setattr(settings, "orgs_enabled", False)
    assert resolve_org_context(OUTSIDER, org["id"]) is None
    assert resolve_org_context(OWNER, None) is None


def test_resolve_org_context_rules(store, orgs_on):
    org = _seed_org(store)
    assert resolve_org_context(MEMBER, None) is None
    with pytest.raises(OrgNotFound):
        resolve_org_context(OUTSIDER, org["id"])
    assert resolve_org_context(VIEWER, org["id"]) == {"org_id": org["id"], "role": "viewer"}   # read access
    assert resolve_org_context(MEMBER, org["id"]) == {"org_id": org["id"], "role": "member"}
    from app.api.org_context import get_org_write_context
    with pytest.raises(HTTPException) as denied:                                                # ...but no saving
        get_org_write_context({"org_id": org["id"], "role": "viewer"})
    assert denied.value.status_code == 403
    assert get_org_write_context({"org_id": org["id"], "role": "member"})["role"] == "member"
    assert get_org_write_context(None) is None


def test_get_org_context_dependency(store, orgs_on):
    from app.api.org_context import get_org_context
    org = _seed_org(store)
    assert get_org_context({"id": MEMBER}, None) is None
    with pytest.raises(HTTPException) as bad:
        get_org_context({"id": MEMBER}, "not-a-uuid")
    assert bad.value.status_code == 400
    with pytest.raises(HTTPException) as missing:
        get_org_context({"id": OUTSIDER}, org["id"])
    assert missing.value.status_code == 404
    assert get_org_context({"id": MEMBER}, org["id"])["org_id"] == org["id"]


def test_org_claims_listing_carries_author(store):
    org = _seed_org(store)
    store["user_claims"].extend([
        {"id": "c1", "user_id": MEMBER, "org_id": org["id"], "claim_description": "MRI denied",
         "cost_breakdown_json": {}, "appeal_output_json": {"appeal_recommendation": "APPEAL"},
         "route_decision": "denied", "created_at": "2026-09-02T00:00:00+00:00"},
        {"id": "c2", "user_id": MEMBER, "org_id": None, "claim_description": "personal", "route_decision": "approved"},
    ])
    rows = list_org_claims(org["id"])
    assert [r["id"] for r in rows] == ["c1"]
    assert rows[0]["created_by_email"] == EMAIL[MEMBER] and rows[0]["appeal_output"]["appeal_recommendation"] == "APPEAL"


def test_user_data_omits_org_id_unless_set(store):
    personal = user_data.create_user_claim("u1", "A denied MRI claim that needs help.", None, None, "denied")
    assert "org_id" not in personal
    scoped = user_data.create_user_claim("u1", "A denied MRI claim that needs help.", None, None, "denied", org_id="org-1")
    assert scoped["org_id"] == "org-1"
    assert "org_id" not in user_data.create_user_policy("u2", {"plan_name": "X"})
    assert user_data.create_user_policy("u2", {"plan_name": "X"}, org_id="org-2")["org_id"] == "org-2"


# ── HTTP surface ─────────────────────────────────────────────────

@pytest.fixture
def client(store, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.auth import get_current_user
    from app.security import rate_limit
    from app.api import org_routes

    current = {"id": OWNER, "email": EMAIL[OWNER]}
    app.dependency_overrides[get_current_user] = lambda: current
    rate_limit._buckets.clear()
    sent = []

    class _Mail:
        configured = False

        def send_org_invitation(self, **kw):
            sent.append(kw)
            return self.configured

    mail = _Mail()
    monkeypatch.setattr(org_routes, "get_email_service", lambda: mail)
    try:
        yield SimpleNamespace(http=TestClient(app), user=current, mail=mail, sent=sent)
    finally:
        app.dependency_overrides.clear()


def test_routes_require_authentication(store):
    from fastapi.testclient import TestClient
    from app.main import app
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        http = TestClient(app)
        for method, path in (("get", "/api/orgs"), ("post", "/api/orgs"), ("get", "/api/orgs/status"),
                             ("get", f"/api/orgs/{uuid4()}/members"), ("post", "/api/orgs/invitations/accept")):
            res = http.request(method.upper(), path, json={"name": "x", "token": "t" * 20})
            assert res.status_code in (401, 403), path
    finally:
        app.dependency_overrides.update(saved)


def test_routes_are_invisible_when_disabled(client, store, monkeypatch):
    monkeypatch.setattr(settings, "orgs_enabled", False)
    assert client.http.get("/api/orgs/status").json() == {"enabled": False}
    assert client.http.get("/api/orgs").status_code == 404
    assert client.http.post("/api/orgs", json={"name": "Acme"}).status_code == 404
    assert client.http.get(f"/api/orgs/{uuid4()}/claims").status_code == 404
    assert store["organizations"] == []


def test_full_team_flow_over_http(client, orgs_on, store):
    http = client.http
    assert http.get("/api/orgs/status").json() == {"enabled": True}
    assert http.get("/api/orgs").json() == []

    created = http.post("/api/orgs", json={"name": "  Acme   Advocates "})
    assert created.status_code == 201, created.text
    org = created.json()
    assert org["name"] == "Acme Advocates" and org["role"] == "owner" and org["member_count"] == 1
    oid = org["id"]

    assert http.post("/api/orgs", json={"name": "A"}).status_code == 422       # too short
    assert http.get(f"/api/orgs/{uuid4()}").status_code == 404                  # unknown org
    assert http.get("/api/orgs/not-a-uuid").status_code == 404                  # never reaches the DB

    # Email not configured → link handed back once to the admin
    inv = http.post(f"/api/orgs/{oid}/invitations", json={"email": EMAIL[MEMBER], "role": "member"})
    assert inv.status_code == 201, inv.text
    body = inv.json()
    assert body["email_sent"] is False and body["accept_url"].startswith(settings.app_base_url.rstrip("/") + "/invite?token=")
    assert client.sent[0]["org_name"] == "Acme Advocates" and client.sent[0]["inviter_email"] == EMAIL[OWNER]
    token = body["accept_url"].split("token=", 1)[1]
    assert http.get(f"/api/orgs/{oid}/invitations").json()[0]["email"] == EMAIL[MEMBER]

    # With email configured the raw link is never returned
    client.mail.configured = True
    inv2 = http.post(f"/api/orgs/{oid}/invitations", json={"email": EMAIL[VIEWER], "role": "viewer"}).json()
    assert inv2["email_sent"] is True and inv2["accept_url"] is None
    assert http.post(f"/api/orgs/{oid}/invitations", json={"email": "bad-address", "role": "member"}).status_code == 422
    assert http.post(f"/api/orgs/{oid}/invitations", json={"email": "x@y.test", "role": "owner"}).status_code == 422

    # Invitee signs in and previews/accepts
    client.user.update({"id": MEMBER, "email": EMAIL[MEMBER]})
    assert http.get(f"/api/orgs/{oid}/members").status_code == 404             # not a member yet → hidden
    preview = http.get("/api/orgs/invitations/preview", params={"token": token}).json()
    assert preview["status"] == "valid" and preview["org_name"] == "Acme Advocates" and preview["role"] == "member"
    accepted = http.post("/api/orgs/invitations/accept", json={"token": token})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "member" and accepted.json()["id"] == oid
    assert http.get(f"/api/orgs/{oid}").json()["member_count"] == 2
    members = http.get(f"/api/orgs/{oid}/members").json()
    assert [(m["role"], m["is_you"]) for m in members] == [("owner", False), ("member", True)]

    # A member cannot invite, rename or delete
    assert http.post(f"/api/orgs/{oid}/invitations", json={"email": "z@z.test", "role": "viewer"}).status_code == 403
    assert http.patch(f"/api/orgs/{oid}", json={"name": "Renamed"}).status_code == 403
    assert http.delete(f"/api/orgs/{oid}").status_code == 403
    # ...but may see workspace claims
    store["user_claims"].append({"id": "c1", "user_id": MEMBER, "org_id": oid, "claim_description": "d",
                                 "route_decision": "denied", "created_at": "2026-09-02T00:00:00+00:00"})
    claims = http.get(f"/api/orgs/{oid}/claims").json()
    assert claims[0]["created_by_email"] == EMAIL[MEMBER]

    # Owner promotes, renames, then the member leaves
    client.user.update({"id": OWNER, "email": EMAIL[OWNER]})
    assert http.patch(f"/api/orgs/{oid}/members/{MEMBER}", json={"role": "admin"}).json()["role"] == "admin"
    assert http.patch(f"/api/orgs/{oid}/members/{MEMBER}", json={"role": "owner"}).status_code == 422
    assert http.patch(f"/api/orgs/{oid}", json={"name": "Acme Advocates Inc"}).json()["name"] == "Acme Advocates Inc"
    assert http.delete(f"/api/orgs/{oid}/members/{OWNER}").status_code == 400  # owner cannot leave
    client.user.update({"id": MEMBER, "email": EMAIL[MEMBER]})
    assert http.delete(f"/api/orgs/{oid}/members/{MEMBER}").json()["success"] is True
    assert http.get(f"/api/orgs/{oid}").status_code == 404

    # Owner deletes the workspace
    client.user.update({"id": OWNER, "email": EMAIL[OWNER]})
    assert http.delete(f"/api/orgs/{oid}").json() == {"success": True, "deleted_id": oid}
    assert http.get("/api/orgs").json() == []
