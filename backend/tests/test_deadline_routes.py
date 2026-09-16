"""
Deadline tracker authorization: every mutation and the breach-letter read must be
scoped to the signed-in owner (the backend uses the service role, so RLS cannot do
this), and a missing/foreign deadline must surface as 404, not 500.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import deadline_routes
from app.api.auth import get_current_user
from fake_supabase import FakeClient

ME, THEM = str(uuid4()), str(uuid4())
MINE, THEIRS = str(uuid4()), str(uuid4())


def _deadline(id_, user_id):
    return {
        "id": id_, "user_id": user_id, "carrier_name": "Acme Health", "appeal_level": "internal_1",
        "appeal_framework": "ERISA_INTERNAL", "state_code": "CA", "date_denial_received": "2026-08-01",
        "deadline_date": "2027-01-28", "statutory_days": 180, "status": "pending",
        "insurer_response_deadline": "2026-08-15", "claim_summary": "MRI denied", "created_at": "2026-08-02T00:00:00+00:00",
    }


@pytest.fixture
def client(monkeypatch):
    from app.main import app
    store = {"appeal_deadlines": [_deadline(MINE, ME), _deadline(THEIRS, THEM)]}
    monkeypatch.setattr(deadline_routes, "get_supabase_client", lambda: FakeClient(store))

    def _llm_must_not_run(*a, **k):
        raise AssertionError("LLM must not be invoked for a deadline the caller does not own")
    monkeypatch.setattr(deadline_routes, "get_llm", _llm_must_not_run)

    app.dependency_overrides[get_current_user] = lambda: {"id": ME, "email": "me@x.test"}
    try:
        yield SimpleNamespace(http=TestClient(app), store=store)
    finally:
        app.dependency_overrides.clear()


def test_list_returns_only_own_deadlines(client):
    body = client.http.get("/api/deadlines").json()
    assert [d["id"] for d in body["deadlines"]] == [MINE]


def test_update_is_scoped_to_owner(client):
    res = client.http.patch(f"/api/deadlines/{THEIRS}", json={"status": "filed"})
    assert res.status_code == 404, res.text                       # not 500, not 200
    theirs = next(d for d in client.store["appeal_deadlines"] if d["id"] == THEIRS)
    assert theirs["status"] == "pending"                          # untouched

    res = client.http.patch(f"/api/deadlines/{MINE}", json={"status": "filed", "date_appeal_filed": "2026-08-10"})
    assert res.status_code == 200 and res.json()["deadline"]["status"] == "filed"
    assert client.http.patch(f"/api/deadlines/{uuid4()}", json={"status": "filed"}).status_code == 404
    assert client.http.patch(f"/api/deadlines/{THEIRS}", json={}).json() == {"success": True}   # no-op stays a no-op


def test_delete_is_scoped_to_owner(client):
    assert client.http.delete(f"/api/deadlines/{THEIRS}").status_code == 404
    assert len(client.store["appeal_deadlines"]) == 2
    assert client.http.delete(f"/api/deadlines/{MINE}").json() == {"success": True}
    assert [d["id"] for d in client.store["appeal_deadlines"]] == [THEIRS]


def test_breach_letter_never_reads_foreign_deadlines(client):
    res = client.http.post(f"/api/deadlines/{THEIRS}/breach-letter")
    assert res.status_code == 404, res.text
    assert client.http.post(f"/api/deadlines/{uuid4()}/breach-letter").status_code == 404
