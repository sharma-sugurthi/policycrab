"""
Admin Analytics & Platform Usage Console — role-gated endpoints for platform telemetry.
"""

import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.api.auth import get_current_user
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin Analytics"])


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Validate that the authenticated user is an authorized admin."""
    user_email = user.get("email", "").strip().lower()
    if not user_email or user_email not in settings.parsed_admin_emails:
        logger.warning(f"Unauthorized admin access attempt by user: {user_email or user.get('id')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required.",
        )
    return user


@router.get("/check")
async def check_admin_status(user: dict = Depends(get_current_user)):
    """Check if the current logged-in user has admin rights."""
    user_email = user.get("email", "").strip().lower()
    is_admin = bool(user_email and user_email in settings.parsed_admin_emails)
    return {"is_admin": is_admin, "email": user_email}


@router.get("/stats")
async def get_admin_stats(user: dict = Depends(require_admin)):
    """Get high-level platform aggregation statistics."""
    client = get_supabase_client()
    try:
        # Get count of total users from Auth
        users_list = client.auth.admin.list_users()
        total_users = len(users_list) if isinstance(users_list, list) else len(getattr(users_list, "users", []))
    except Exception as e:
        logger.error(f"Error fetching auth users count: {e}")
        total_users = 0

    def get_table_count(table_name: str) -> int:
        try:
            res = client.table(table_name).select("id", count="exact").limit(1).execute()
            return res.count or 0
        except Exception as err:
            logger.warning(f"Error fetching count for {table_name}: {err}")
            return 0

    total_policies = get_table_count("user_policies")
    total_claims = get_table_count("user_claims")
    total_documents = get_table_count("user_documents")
    total_audits = get_table_count("user_audits")
    total_chats = get_table_count("user_chats")

    return {
        "total_users": total_users,
        "total_policies": total_policies,
        "total_claims": total_claims,
        "total_documents": total_documents,
        "total_audits": total_audits,
        "total_chats": total_chats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/activity")
async def get_admin_activity(days: int = 30, user: dict = Depends(require_admin)):
    """Get daily platform usage breakdown over the specified time window."""
    client = get_supabase_client()
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    start_iso = start_date.isoformat()

    # Initialize bucket dictionary for each date string in the window
    date_buckets = {}
    for i in range(days):
        dt = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        date_buckets[dt] = {"date": dt, "documents": 0, "audits": 0, "claims": 0, "new_users": 0}

    def fetch_dates(table_name: str, key_name: str):
        try:
            res = client.table(table_name).select("created_at").gte("created_at", start_iso).execute()
            for row in (res.data or []):
                dt = str(row.get("created_at", ""))[:10]
                if dt in date_buckets:
                    date_buckets[dt][key_name] += 1
        except Exception as e:
            logger.warning(f"Error fetching dates from {table_name}: {e}")

    fetch_dates("user_documents", "documents")
    fetch_dates("user_audits", "audits")
    fetch_dates("user_claims", "claims")

    # Count new user registrations in the activity buckets
    try:
        users_list = client.auth.admin.list_users()
        items = users_list if isinstance(users_list, list) else getattr(users_list, "users", [])
        for u in items:
            u_dict = u.model_dump() if hasattr(u, "model_dump") else u.__dict__
            dt = str(u_dict.get("created_at", ""))[:10]
            if dt in date_buckets:
                date_buckets[dt]["new_users"] += 1
    except Exception as e:
        logger.warning(f"Error checking user creation dates: {e}")

    return {
        "window_days": days,
        "activity_timeline": list(date_buckets.values())
    }


@router.get("/users")
async def get_admin_users(user: dict = Depends(require_admin)):
    """Get a detailed list of platform users and their feature usage counts."""
    client = get_supabase_client()
    try:
        users_list = client.auth.admin.list_users()
        items = users_list if isinstance(users_list, list) else getattr(users_list, "users", [])
    except Exception as e:
        logger.error(f"Error fetching users list: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve platform users.")

    # Aggregate counts per user_id from database tables
    doc_counts = {}
    audit_counts = {}
    claim_counts = {}
    policy_counts = {}

    def populate_counts(table_name: str, count_dict: dict):
        try:
            res = client.table(table_name).select("user_id").execute()
            for row in (res.data or []):
                uid = str(row.get("user_id"))
                count_dict[uid] = count_dict.get(uid, 0) + 1
        except Exception as err:
            logger.warning(f"Error aggregating counts for {table_name}: {err}")

    populate_counts("user_documents", doc_counts)
    populate_counts("user_audits", audit_counts)
    populate_counts("user_claims", claim_counts)
    populate_counts("user_policies", policy_counts)

    user_profiles = []
    for u in items:
        u_data = u.model_dump() if hasattr(u, "model_dump") else u.__dict__
        uid = str(u_data.get("id"))
        email = str(u_data.get("email") or "N/A")
        metadata = u_data.get("user_metadata") or {}
        full_name = metadata.get("full_name") or metadata.get("name") or "Unnamed"
        created_at = str(u_data.get("created_at", ""))
        last_sign_in = str(u_data.get("last_sign_in_at") or created_at)

        user_profiles.append({
            "id": uid,
            "email": email,
            "full_name": full_name,
            "created_at": created_at,
            "last_sign_in_at": last_sign_in,
            "documents_count": doc_counts.get(uid, 0),
            "audits_count": audit_counts.get(uid, 0),
            "claims_count": claim_counts.get(uid, 0),
            "policies_count": policy_counts.get(uid, 0),
        })

    user_profiles.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"users": user_profiles, "count": len(user_profiles)}
