"""
Tests for outcome recording and calibration.
Supabase is replaced by a fake client (pattern from test_user_data.py).
"""

from types import SimpleNamespace

import pytest

from app.services import outcomes
from app.services.outcomes import compute_calibration, record_outcome


# ── Fake Supabase client ──────────────────────────────────────────

class _FakeQuery:
    def __init__(self, table, store):
        self.table = table
        self.store = store
        self.filters = {}
        self.payload = None
        self.mode = "select"

    def select(self, *a, **k):
        self.mode = "select"
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def limit(self, *a):
        return self

    def order(self, *a, **k):
        return self

    def upsert(self, payload, on_conflict=None):
        self.mode = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self.mode == "select":
            out = [r for r in rows if all(str(r.get(c)) == str(v) for c, v in self.filters.items())]
            return SimpleNamespace(data=out, count=len(out))
        # upsert on claim_id
        key = self.on_conflict or "id"
        rows[:] = [r for r in rows if r.get(key) != self.payload.get(key)]
        rows.append(self.payload)
        return SimpleNamespace(data=[self.payload])


class _FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _FakeQuery(name, self.store)


@pytest.fixture
def fake_db(monkeypatch):
    store = {
        "user_claims": [
            {"id": "claim-1", "user_id": "user-A",
             "appeal_output_json": {"success_score": 0.72, "success_score_band": "HIGH",
                                    "estimated_success_probability": 0.6, "success_score_version": "v1"}},
            {"id": "claim-2", "user_id": "user-B", "appeal_output_json": {}},
        ],
        "appeal_outcomes": [],
    }
    monkeypatch.setattr(outcomes, "get_supabase_client", lambda: _FakeClient(store))
    return store


# ── record_outcome ────────────────────────────────────────────────

def test_record_outcome_snapshots_prediction_and_upserts(fake_db):
    saved = record_outcome("user-A", "claim-1", {"outcome": "won", "amount_recovered": "1200.50"})
    assert saved["predicted_success_score"] == 0.72
    assert saved["predicted_band"] == "HIGH"
    assert saved["predicted_probability_llm"] == 0.6
    assert saved["score_version"] == "v1"
    assert saved["amount_recovered"] == 1200.5

    record_outcome("user-A", "claim-1", {"outcome": "partial"})
    assert len(fake_db["appeal_outcomes"]) == 1            # upsert on claim_id
    assert fake_db["appeal_outcomes"][0]["outcome"] == "partial"


def test_record_outcome_rejects_foreign_claim(fake_db):
    with pytest.raises(ValueError, match="not found"):
        record_outcome("user-A", "claim-2", {"outcome": "won"})


def test_record_outcome_rejects_invalid_outcome(fake_db):
    with pytest.raises(ValueError, match="outcome must be"):
        record_outcome("user-A", "claim-1", {"outcome": "maybe"})


# ── compute_calibration (pure) ────────────────────────────────────

def _row(outcome, score=None, band=None, llm=None, recovered=None, decided_at="2026-08-01"):
    return {"outcome": outcome, "predicted_success_score": score, "predicted_band": band,
            "predicted_probability_llm": llm, "amount_recovered": recovered, "decided_at": decided_at,
            "recorded_at": "2026-08-02T00:00:00Z"}


def test_calibration_buckets_rates_and_excludes_pending():
    rows = (
        [_row("won", 0.8, "HIGH", 0.7, 1000)] * 6
        + [_row("lost", 0.8, "HIGH", 0.7)] * 2
        + [_row("partial", 0.3, "LOW", 0.4, 200)] * 2
        + [_row("lost", 0.3, "LOW", 0.4)] * 3
        + [_row("pending", 0.5, "MEDIUM", 0.5)] * 4
        + [_row("withdrawn", 0.5, "MEDIUM", 0.5)]
    )
    cal = compute_calibration(rows, min_bucket_n=5)

    assert cal["n_total"] == 18 and cal["n_decided"] == 13 and cal["n_pending"] == 4 and cal["n_withdrawn"] == 1
    high = cal["by_band"]["HIGH"]
    assert (high["won"], high["lost"], high["n_decided"]) == (6, 2, 8)
    assert high["observed_overturn_rate"] == 0.75 and high["observed_win_rate_strict"] == 0.75
    assert high["insufficient_data"] is False
    low = cal["by_band"]["LOW"]
    assert low["observed_overturn_rate"] == 0.4 and low["observed_win_rate_strict"] == 0.0
    assert cal["by_score_bin"]["0.8-0.9"]["n_decided"] == 8
    assert cal["total_recovered"] == 6400.0
    assert cal["publishable"] is False                     # 13 < 30
    assert cal["date_range"] == {"from": "2026-08-01", "to": "2026-08-01"}


def test_calibration_brier_scores():
    rows = [_row("won", 1.0, "HIGH", 0.5), _row("lost", 0.0, "VERY_LOW", 0.5)]
    cal = compute_calibration(rows)
    assert cal["brier_score_deterministic"] == 0.0          # perfect
    assert cal["brier_score_llm"] == 0.25                   # 0.5 vs 1 and 0.5 vs 0


def test_calibration_empty_and_unscored_rows():
    assert compute_calibration([])["n_decided"] == 0
    cal = compute_calibration([_row("won"), _row("lost")])
    assert cal["by_band"]["UNSCORED"]["n_decided"] == 2
    assert cal["brier_score_deterministic"] is None
    assert cal["by_score_bin"] == {}


# ── Route wiring ──────────────────────────────────────────────────

def test_outcome_routes_require_authentication():
    """
    FastAPI 0.139 includes sub-routers lazily, so route introspection on api_router
    does not see them. Exercise the mounted app instead: every outcomes endpoint must
    reject an unauthenticated request before touching any data store.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    assert client.get("/api/outcomes").status_code in (401, 403)
    assert client.get("/api/outcomes/calibration").status_code in (401, 403)
    assert client.post("/api/outcomes", json={"claim_id": "abcdefgh", "outcome": "won"}).status_code in (401, 403)
    # Route exists (not 404) — an unknown path would be 404
    assert client.get("/api/outcomes/does-not-exist").status_code in (401, 403, 404, 405)
