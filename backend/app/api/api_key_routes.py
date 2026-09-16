"""
API key management — personal keys (/api/api-keys) and workspace keys
(/api/orgs/{org_id}/api-keys, owners and admins). Keys can never manage keys:
these routes are absent from the key-callable allowlist and refuse key auth.
Every endpoint answers 404 while API_KEYS_ENABLED is false.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth import get_current_user
from app.api.org_context import translate_org_error, valid_uuid_or_404
from app.models.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut, ApiKeysStatus
from app.security.rate_limit import rate_limit_user
from app.services import api_keys as key_service
from app.services import organizations as org_service
from app.services.api_keys import ApiKeyError
from app.services.audit_trail import record_audit
from app.services.organizations import OrgError, OrgNotFound, OrgPermissionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])
org_router = APIRouter(prefix="/api/orgs", tags=["API Keys"])

KEY_CREATE_RATE_LIMIT = rate_limit_user("api-keys:create", max_requests=10, window_seconds=3600)


def require_api_keys_enabled(user: dict = Depends(get_current_user)) -> None:
    """404 when the feature is off — evaluated only after authentication so the flag is never leaked."""
    if not key_service.api_keys_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API keys are not enabled on this deployment.")


def require_human(user: dict = Depends(get_current_user)) -> dict:
    """Key management needs a signed-in person, never another key."""
    if user.get("auth_method") == "api_key":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API keys cannot manage API keys.")
    return user


def _out(row: dict) -> ApiKeyOut:
    return ApiKeyOut(
        id=str(row.get("id")), name=row.get("name") or "", key_prefix=row.get("key_prefix") or "",
        scopes=list(row.get("scopes") or []), environment=row.get("environment") or "live",
        user_id=str(row.get("user_id") or ""), owner_email=row.get("owner_email"),
        org_id=str(row["org_id"]) if row.get("org_id") else None,
        last_used_at=row.get("last_used_at"), expires_at=row.get("expires_at"), revoked_at=row.get("revoked_at"),
        created_at=row.get("created_at"), active=bool(row.get("active", True)),
    )


def _create(body: ApiKeyCreate, user: dict, org_id: str | None, request: Request) -> ApiKeyCreated:
    try:
        row, raw = key_service.create_api_key(
            user["id"], user.get("email"), body.name, body.scopes,
            org_id=org_id, environment=body.environment, expires_in_days=body.expires_in_days,
        )
    except ApiKeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit("api_key.created", user_id=user["id"], org_id=org_id, resource_type="api_key", resource_id=row["id"],
                 metadata={"environment": body.environment, "scopes": ",".join(body.scopes), "name": body.name},
                 request=request)
    return ApiKeyCreated(key=raw, api_key=_out(row))


# ── Feature status & scopes ──────────────────────────────────────────

@router.get("/scopes", response_model=ApiKeysStatus)
async def api_key_scopes(user: dict = Depends(get_current_user)):
    """Whether API keys are enabled here, and the scopes a key can be granted."""
    enabled = key_service.api_keys_enabled()
    return ApiKeysStatus(enabled=enabled, scopes=dict(key_service.SCOPE_DESCRIPTIONS) if enabled else {})


# ── Personal keys ────────────────────────────────────────────────────

@router.get("", response_model=list[ApiKeyOut])
async def list_personal_keys(user: dict = Depends(require_human), _flag: None = Depends(require_api_keys_enabled)):
    return [_out(r) for r in key_service.list_api_keys(user_id=user["id"])]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_personal_key(
    body: ApiKeyCreate,
    request: Request,
    user: dict = Depends(require_human),
    _flag: None = Depends(require_api_keys_enabled),
    _rl: None = Depends(KEY_CREATE_RATE_LIMIT),
):
    """Create a personal key. The full key is returned once and never again."""
    return _create(body, user, None, request)


@router.delete("/{key_id}")
async def revoke_personal_key(
    key_id: str,
    request: Request,
    user: dict = Depends(require_human),
    _flag: None = Depends(require_api_keys_enabled),
):
    key_id = valid_uuid_or_404(key_id, "API key")
    row = key_service.revoke_api_key(key_id, user_id=user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found.")
    record_audit("api_key.revoked", user_id=user["id"], resource_type="api_key", resource_id=key_id, request=request)
    return {"success": True, "revoked_id": key_id}


# ── Workspace keys (owners and admins) ───────────────────────────────

def _admin_membership(org_id: str, user: dict) -> dict:
    org_id = valid_uuid_or_404(org_id)
    try:
        return org_service.require_membership(org_id, user["id"], minimum="admin")
    except (OrgNotFound, OrgPermissionError, OrgError) as exc:
        raise translate_org_error(exc) from exc


@org_router.get("/{org_id}/api-keys", response_model=list[ApiKeyOut])
async def list_org_keys(org_id: str, user: dict = Depends(require_human), _flag: None = Depends(require_api_keys_enabled)):
    _admin_membership(org_id, user)
    return [_out(r) for r in key_service.list_api_keys(org_id=org_id)]


@org_router.post("/{org_id}/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_org_key(
    org_id: str,
    body: ApiKeyCreate,
    request: Request,
    user: dict = Depends(require_human),
    _flag: None = Depends(require_api_keys_enabled),
    _rl: None = Depends(KEY_CREATE_RATE_LIMIT),
):
    """Create a workspace key. Requests made with it run as you, inside this workspace."""
    _admin_membership(org_id, user)
    return _create(body, user, org_id, request)


@org_router.delete("/{org_id}/api-keys/{key_id}")
async def revoke_org_key(
    org_id: str,
    key_id: str,
    request: Request,
    user: dict = Depends(require_human),
    _flag: None = Depends(require_api_keys_enabled),
):
    _admin_membership(org_id, user)
    key_id = valid_uuid_or_404(key_id, "API key")
    row = key_service.revoke_api_key(key_id, org_id=org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found.")
    record_audit("api_key.revoked", user_id=user["id"], org_id=org_id, resource_type="api_key", resource_id=key_id,
                 request=request)
    return {"success": True, "revoked_id": key_id}
