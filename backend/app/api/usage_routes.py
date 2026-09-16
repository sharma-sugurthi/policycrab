"""
Usage metering API — what a user or workspace consumed, and a platform rollup for admins.
Read-only; rows are written by the metering middleware.
"""

from fastapi import APIRouter, Depends, Query

from app.api.admin_routes import require_admin
from app.api.auth import get_current_user
from app.api.org_context import translate_org_error, valid_uuid_or_404
from app.services import organizations as org_service
from app.services import usage as usage_service
from app.services.organizations import OrgError, OrgNotFound, OrgPermissionError

router = APIRouter(prefix="/api/usage", tags=["Usage"])
admin_router = APIRouter(prefix="/api/admin", tags=["Admin Analytics"])

_DAYS = Query(30, ge=1, le=365)


def _disabled(scope: dict) -> dict:
    return {"enabled": False, "scope": scope, "total": 0, "by_type": {}, "by_day": [], "event_types": []}


@router.get("/me")
async def my_usage(days: int = _DAYS, user: dict = Depends(get_current_user)):
    """Billable actions recorded for the signed-in user (personal and workspace)."""
    if not usage_service.metering_enabled():
        return _disabled({"type": "user", "id": user["id"]})
    out = usage_service.summarize_user_usage(user["id"], days)
    out["enabled"] = True
    return out


@router.get("/org/{org_id}")
async def org_usage(org_id: str, days: int = _DAYS, user: dict = Depends(get_current_user)):
    """Workspace consumption; owners and admins only."""
    org_id = valid_uuid_or_404(org_id)
    try:
        org_service.require_membership(org_id, user["id"], minimum="admin")
    except (OrgNotFound, OrgPermissionError, OrgError) as exc:
        raise translate_org_error(exc) from exc
    if not usage_service.metering_enabled():
        return _disabled({"type": "org", "id": org_id})
    out = usage_service.summarize_org_usage(org_id, days)
    out["enabled"] = True
    return out


@admin_router.get("/usage")
async def platform_usage(
    days: int = _DAYS,
    group: str = Query("org", pattern="^(org|user)$"),
    user: dict = Depends(require_admin),
):
    """Platform-wide usage rollup grouped by organization or user (admin only)."""
    if not usage_service.metering_enabled():
        return {"enabled": False, "group_by": group, "groups": [], "total": 0, "by_type": {}, "by_day": []}
    out = usage_service.summarize_global_usage(days, group)
    out["enabled"] = True
    return out
