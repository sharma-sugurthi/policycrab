import logging
from datetime import datetime, timezone

from app.services.supabase_client import get_supabase_client
from app.security.phi_scrubber import scrub_phi

logger = logging.getLogger(__name__)


def create_user_policy(user_id: str, policy_profile: dict) -> dict | None:
    client = get_supabase_client()
    result = (
        client.table("user_policies")
        .insert({"user_id": user_id, "policy_profile_json": policy_profile})
        .execute()
    )
    return result.data[0] if result.data else None


def list_user_policies(user_id: str) -> list[dict]:
    client = get_supabase_client()
    result = (
        client.table("user_policies")
        .select("id, policy_profile_json, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def create_user_claim(
    user_id: str,
    claim_description: str,
    cost_breakdown: dict | None,
    appeal_output: dict | None,
    route_decision: str | None,
    policy_id: str | None = None,
) -> dict | None:
    # Scrub PHI from freetext before writing to DB
    clean_description, redaction_count = scrub_phi(claim_description)
    if redaction_count:
        logger.info(
            f"create_user_claim: {redaction_count} PHI pattern(s) redacted "
            f"from claim description before DB write (user={user_id})"
        )

    client = get_supabase_client()
    payload = {
        "user_id": user_id,
        "policy_id": policy_id,
        "claim_description": clean_description,
        "cost_breakdown_json": cost_breakdown,
        "appeal_output_json": appeal_output,
        "route_decision": route_decision,
    }
    result = client.table("user_claims").insert(payload).execute()
    return result.data[0] if result.data else None


def list_user_claims(user_id: str) -> list[dict]:
    client = get_supabase_client()
    result = (
        client.table("user_claims")
        .select("id, claim_description, cost_breakdown_json, appeal_output_json, route_decision, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def get_user_chat(user_id: str) -> dict | None:
    client = get_supabase_client()
    result = (
        client.table("user_chats")
        .select("id, messages, policy_profile_json, cost_breakdown_json, created_at, updated_at")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def upsert_user_chat(
    user_id: str,
    messages: list[dict],
    policy_profile: dict | None = None,
    cost_breakdown: dict | None = None,
) -> dict | None:
    client = get_supabase_client()
    payload = {
        "user_id": user_id,
        "messages": messages,
        "policy_profile_json": policy_profile,
        "cost_breakdown_json": cost_breakdown,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("user_chats").upsert(payload, on_conflict="user_id").execute()
    return result.data[0] if result.data else None


def clear_user_chat(user_id: str) -> None:
    client = get_supabase_client()
    client.table("user_chats").delete().eq("user_id", user_id).execute()
