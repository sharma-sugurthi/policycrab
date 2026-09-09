"""
Appeal outcome persistence + calibration (pure aggregation).

record_outcome() verifies the claim belongs to the caller, snapshots the
prediction fields from user_claims.appeal_output_json, and upserts one row per
claim into appeal_outcomes (migration 008).

compute_calibration() is pure Python over rows — testable without Supabase — and
produces the honest "observed overturn rate vs predicted" table.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

VALID_OUTCOMES = ("won", "partial", "lost", "pending", "withdrawn")
DECIDED_OUTCOMES = ("won", "partial", "lost")
MIN_PUBLISHABLE_N = 30


def _num(value) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _fetch_owned_claim(client, user_id: str, claim_id: str) -> dict | None:
    result = (
        client.table("user_claims")
        .select("id, user_id, appeal_output_json")
        .eq("id", claim_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def record_outcome(user_id: str, claim_id: str, payload: dict) -> dict | None:
    """
    Upsert an outcome for one of the caller's claims.
    Raises ValueError when the claim is not owned by the user or the outcome is invalid.
    """
    outcome = str(payload.get("outcome") or "").lower()
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {', '.join(VALID_OUTCOMES)}")

    client = get_supabase_client()
    claim = _fetch_owned_claim(client, user_id, claim_id)
    if not claim:
        raise ValueError("Claim not found or not owned by you.")

    ao = claim.get("appeal_output_json") or {}
    if not isinstance(ao, dict):
        ao = {}

    row = {
        "id": str(uuid4()),
        "user_id": user_id,
        "claim_id": claim_id,
        "outcome": outcome,
        "amount_recovered": _num(payload.get("amount_recovered")),
        "amount_at_stake": _num(payload.get("amount_at_stake")),
        "appeal_level": payload.get("appeal_level"),
        "decided_at": payload.get("decided_at"),
        "notes": (str(payload.get("notes"))[:2000] if payload.get("notes") else None),
        # prediction snapshot — never recomputed later
        "predicted_success_score": _num(ao.get("success_score")),
        "predicted_band": ao.get("success_score_band"),
        "predicted_probability_llm": _num(ao.get("estimated_success_probability")),
        "score_version": ao.get("success_score_version"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("appeal_outcomes").upsert(row, on_conflict="claim_id").execute()
    saved = result.data[0] if result.data else row
    logger.info(f"Outcome recorded: claim={claim_id} outcome={outcome} (user={user_id})")
    return saved


def list_outcomes(user_id: str) -> list[dict]:
    client = get_supabase_client()
    result = (
        client.table("appeal_outcomes")
        .select(
            "id, claim_id, outcome, amount_recovered, amount_at_stake, appeal_level, decided_at, notes, "
            "predicted_success_score, predicted_band, predicted_probability_llm, score_version, recorded_at"
        )
        .eq("user_id", user_id)
        .order("recorded_at", desc=True)
        .execute()
    )
    return result.data or []


def fetch_outcomes_for_calibration(user_id: str | None) -> list[dict]:
    """All rows for one user, or every user's rows when user_id is None (admin scope)."""
    client = get_supabase_client()
    query = client.table("appeal_outcomes").select(
        "outcome, predicted_success_score, predicted_band, predicted_probability_llm, "
        "amount_recovered, recorded_at, decided_at"
    )
    if user_id:
        query = query.eq("user_id", user_id)
    result = query.execute()
    return result.data or []


# ── Pure aggregation ──────────────────────────────────────────────

def _outcome_value(outcome: str) -> float:
    return {"won": 1.0, "partial": 0.5, "lost": 0.0}[outcome]


def _bucket_stats(rows: list[dict], min_bucket_n: int, score_key: str) -> dict:
    n = len(rows)
    won = sum(1 for r in rows if r["outcome"] == "won")
    partial = sum(1 for r in rows if r["outcome"] == "partial")
    lost = sum(1 for r in rows if r["outcome"] == "lost")
    decided = won + partial + lost
    scores = [_num(r.get(score_key)) for r in rows]
    scores = [s for s in scores if s is not None]
    return {
        "n_decided": decided,
        "won": won,
        "partial": partial,
        "lost": lost,
        "observed_win_rate_strict": round(won / decided, 3) if decided else None,
        "observed_overturn_rate": round((won + partial) / decided, 3) if decided else None,
        "mean_predicted": round(sum(scores) / len(scores), 3) if scores else None,
        "insufficient_data": n < min_bucket_n,
    }


def compute_calibration(rows: list[dict], min_bucket_n: int = 10) -> dict:
    """
    Compare predicted success (deterministic score and LLM probability) against
    observed outcomes. Pending/withdrawn rows are excluded from all rates.
    """
    decided = [r for r in rows if r.get("outcome") in DECIDED_OUTCOMES]
    pending = sum(1 for r in rows if r.get("outcome") == "pending")
    withdrawn = sum(1 for r in rows if r.get("outcome") == "withdrawn")

    by_band: dict[str, list[dict]] = {}
    by_score_bin: dict[str, list[dict]] = {}
    by_llm_bin: dict[str, list[dict]] = {}
    for r in decided:
        band = str(r.get("predicted_band") or "UNSCORED")
        by_band.setdefault(band, []).append(r)
        s = _num(r.get("predicted_success_score"))
        if s is not None:
            lo = min(int(s * 10) / 10, 0.9)
            by_score_bin.setdefault(f"{lo:.1f}-{lo + 0.1:.1f}", []).append(r)
        p = _num(r.get("predicted_probability_llm"))
        if p is not None:
            lo = min(int(p * 10) / 10, 0.9)
            by_llm_bin.setdefault(f"{lo:.1f}-{lo + 0.1:.1f}", []).append(r)

    def brier(score_key: str) -> float | None:
        pairs = [(_num(r.get(score_key)), _outcome_value(r["outcome"])) for r in decided]
        pairs = [(p, o) for p, o in pairs if p is not None]
        if not pairs:
            return None
        return round(sum((p - o) ** 2 for p, o in pairs) / len(pairs), 4)

    dates = [r.get("decided_at") or r.get("recorded_at") for r in rows]
    dates = [d for d in dates if d]
    total_recovered = sum(_num(r.get("amount_recovered")) or 0.0 for r in decided)
    overall = _bucket_stats(decided, min_bucket_n=MIN_PUBLISHABLE_N, score_key="predicted_success_score")

    return {
        "n_total": len(rows),
        "n_decided": len(decided),
        "n_pending": pending,
        "n_withdrawn": withdrawn,
        "overall": overall,
        "publishable": len(decided) >= MIN_PUBLISHABLE_N,
        "min_publishable_n": MIN_PUBLISHABLE_N,
        "total_recovered": round(total_recovered, 2),
        "brier_score_deterministic": brier("predicted_success_score"),
        "brier_score_llm": brier("predicted_probability_llm"),
        "by_band": {k: _bucket_stats(v, min_bucket_n, "predicted_success_score") for k, v in sorted(by_band.items())},
        "by_score_bin": {k: _bucket_stats(v, min_bucket_n, "predicted_success_score") for k, v in sorted(by_score_bin.items())},
        "by_llm_bin": {k: _bucket_stats(v, min_bucket_n, "predicted_probability_llm") for k, v in sorted(by_llm_bin.items())},
        "date_range": {"from": min(dates), "to": max(dates)} if dates else None,
    }
