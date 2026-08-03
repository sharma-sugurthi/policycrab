import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.services.supabase_client import get_supabase_client
from app.security.presidio_scrubber import scrub_phi

logger = logging.getLogger(__name__)


MAX_POLICIES_PER_USER = 5
MAX_DOCUMENTS_PER_USER = 50
MAX_AUDITS_PER_USER = 50


def create_user_policy(
    user_id: str,
    policy_profile: dict,
    session_id: str | None = None,
    raw_text: str | None = None,
) -> dict | None:
    client = get_supabase_client()

    # Enforce per-user policy limit
    existing = count_user_policies(user_id)
    if existing >= MAX_POLICIES_PER_USER:
        logger.warning(
            f"User {user_id} has reached the policy limit ({MAX_POLICIES_PER_USER}). "
            f"Delete an existing policy before uploading a new one."
        )
        raise ValueError(
            f"You have reached the maximum of {MAX_POLICIES_PER_USER} saved policies. "
            f"Please delete an existing policy before uploading a new one."
        )

    payload = {
        "id": str(uuid4()),
        "user_id": user_id,
        "session_id": session_id,
        "policy_profile_json": policy_profile,
        # Store the first 5000 chars of raw text for auditing / re-extraction.
        # None if the caller didn't supply it (text-paste path without raw PDF).
        "raw_text": raw_text[:5000] if raw_text else None,
    }
    result = (
        client.table("user_policies")
        .insert(payload)
        .execute()
    )
    return result.data[0] if result.data else None



def list_user_policies(user_id: str) -> list[dict]:
    client = get_supabase_client()
    result = (
        client.table("user_policies")
        .select("id, session_id, policy_profile_json, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def count_user_policies(user_id: str) -> int:
    """Return the count of policies for a user."""
    client = get_supabase_client()
    result = (
        client.table("user_policies")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return result.count or 0


def delete_user_policy(user_id: str, policy_id: str) -> bool:
    """Delete a policy by ID, scoped to the current user for security."""
    client = get_supabase_client()
    result = (
        client.table("user_policies")
        .delete()
        .eq("id", policy_id)
        .eq("user_id", user_id)  # Security: ensure user owns the policy
        .execute()
    )
    deleted = bool(result.data)
    if deleted:
        logger.info(f"Deleted policy {policy_id} for user {user_id}")
    else:
        logger.warning(f"Policy {policy_id} not found or not owned by user {user_id}")
    return deleted


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
        "id": str(uuid4()),
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


def get_user_chat(user_id: str, chat_id: str) -> dict | None:
    client = get_supabase_client()
    result = (
        client.table("user_chats")
        .select("id, title, messages, policy_profile_json, cost_breakdown_json, created_at, updated_at")
        .eq("user_id", user_id)
        .eq("id", chat_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def list_user_chats(user_id: str) -> list[dict]:
    client = get_supabase_client()
    result = (
        client.table("user_chats")
        .select("id, title, updated_at, created_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data or []


def upsert_user_chat(
    user_id: str,
    messages: list[dict],
    policy_profile: dict | None = None,
    cost_breakdown: dict | None = None,
    chat_id: str | None = None,
    title: str | None = None,
) -> dict | None:
    client = get_supabase_client()
    
    if not chat_id:
        chat_id = str(uuid4())
        
    payload = {
        "id": chat_id,
        "user_id": user_id,
        "messages": messages,
        "policy_profile_json": policy_profile,
        "cost_breakdown_json": cost_breakdown,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    if title:
        payload["title"] = title

    # Upsert based on the 'id' column now, rather than 'user_id'
    result = client.table("user_chats").upsert(payload, on_conflict="id").execute()
    return result.data[0] if result.data else None


def delete_user_chat(user_id: str, chat_id: str) -> bool:
    client = get_supabase_client()
    result = (
        client.table("user_chats")
        .delete()
        .eq("id", chat_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)


def clear_user_chat(user_id: str) -> None:
    client = get_supabase_client()
    client.table("user_chats").delete().eq("user_id", user_id).execute()


# ── Document Vault Persistence ────────────────────────────────────────

def count_user_documents(user_id: str) -> int:
    client = get_supabase_client()
    result = (
        client.table("user_documents")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return result.count or 0


def create_user_document(
    user_id: str,
    filename: str,
    document_type: str,
    extraction_method: str | None,
    extracted_json: dict,
    is_denied: bool | None = False,
    billed_amount: float | None = None,
) -> dict | None:
    client = get_supabase_client()

    if count_user_documents(user_id) >= MAX_DOCUMENTS_PER_USER:
        logger.warning(f"User {user_id} reached document limit ({MAX_DOCUMENTS_PER_USER}).")
        raise ValueError(
            f"You have reached the maximum of {MAX_DOCUMENTS_PER_USER} saved documents. "
            f"Please delete older documents before uploading a new one."
        )

    payload = {
        "id": str(uuid4()),
        "user_id": user_id,
        "filename": filename,
        "document_type": document_type or "unknown",
        "extraction_method": extraction_method,
        "extracted_json": extracted_json,
        "is_denied": bool(is_denied),
        "billed_amount": billed_amount,
    }
    result = client.table("user_documents").insert(payload).execute()
    return result.data[0] if result.data else None


def list_user_documents(user_id: str) -> list[dict]:
    client = get_supabase_client()
    result = (
        client.table("user_documents")
        .select("id, filename, document_type, extraction_method, extracted_json, is_denied, billed_amount, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def delete_user_document(user_id: str, document_id: str) -> bool:
    client = get_supabase_client()
    result = (
        client.table("user_documents")
        .delete()
        .eq("id", document_id)
        .eq("user_id", user_id)
        .execute()
    )
    deleted = bool(result.data)
    if deleted:
        logger.info(f"Deleted document {document_id} for user {user_id}")
    else:
        logger.warning(f"Document {document_id} not found or not owned by user {user_id}")
    return deleted


# ── Bill Auditor Persistence ──────────────────────────────────────────

def count_user_audits(user_id: str) -> int:
    client = get_supabase_client()
    result = (
        client.table("user_audits")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return result.count or 0


def create_user_audit(
    user_id: str,
    service_lines_json: list[dict],
    audit_result_json: dict,
    overall_risk: str = "low",
    total_billed: float = 0.0,
    potential_savings: float | None = None,
    source: str = "manual",
) -> dict | None:
    client = get_supabase_client()

    if count_user_audits(user_id) >= MAX_AUDITS_PER_USER:
        logger.warning(f"User {user_id} reached audit reports limit ({MAX_AUDITS_PER_USER}).")
        raise ValueError(
            f"You have reached the maximum of {MAX_AUDITS_PER_USER} saved audit reports. "
            f"Please delete older reports before running a new audit."
        )

    payload = {
        "id": str(uuid4()),
        "user_id": user_id,
        "service_lines_json": service_lines_json,
        "audit_result_json": audit_result_json,
        "overall_risk": overall_risk or "low",
        "total_billed": total_billed or 0.0,
        "potential_savings": potential_savings,
        "source": source or "manual",
    }
    result = client.table("user_audits").insert(payload).execute()
    return result.data[0] if result.data else None


def list_user_audits(user_id: str) -> list[dict]:
    client = get_supabase_client()
    result = (
        client.table("user_audits")
        .select("id, service_lines_json, audit_result_json, dispute_letter, overall_risk, total_billed, potential_savings, source, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def delete_user_audit(user_id: str, audit_id: str) -> bool:
    client = get_supabase_client()
    result = (
        client.table("user_audits")
        .delete()
        .eq("id", audit_id)
        .eq("user_id", user_id)
        .execute()
    )
    deleted = bool(result.data)
    if deleted:
        logger.info(f"Deleted audit {audit_id} for user {user_id}")
    else:
        logger.warning(f"Audit {audit_id} not found or not owned by user {user_id}")
    return deleted


def update_user_audit_letter(user_id: str, audit_id: str, letter_text: str) -> bool:
    client = get_supabase_client()
    result = (
        client.table("user_audits")
        .update({"dispute_letter": letter_text})
        .eq("id", audit_id)
        .eq("user_id", user_id)
        .execute()
    )
    updated = bool(result.data)
    if updated:
        logger.info(f"Updated dispute letter for audit {audit_id} (user {user_id})")
    else:
        logger.warning(f"Audit {audit_id} not found or not owned by user {user_id}")
    return updated
