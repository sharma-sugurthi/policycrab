from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.services import api_keys as api_key_service
from app.services.audit_trail import record_audit
from app.services.supabase_client import get_supabase_client
import logging

logger = logging.getLogger(__name__)

# Stable UUID for the BENCHMARK_TOKEN bypass — Supabase tables with uuid user_id
# columns will accept this; ad-hoc strings like "benchmark_user" cause 22P02 errors.
BENCHMARK_USER_ID = "00000000-0000-4000-8000-000000000001"


security = HTTPBearer()


def verify_supabase_token(token: str) -> dict:
    """Validate a Supabase JWT token and return the user object."""
    benchmark_auth_enabled = settings.debug or settings.allow_benchmark_auth
    if token in {"BENCHMARK_TOKEN", "Bearer BENCHMARK_TOKEN"}:
        if benchmark_auth_enabled:
            return {"id": BENCHMARK_USER_ID, "email": "benchmark@policycrab.local"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benchmark authentication is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase = get_supabase_client()

    try:
        user_response = supabase.auth.get_user(token)
        if user_response and user_response.user:
            return user_response.user.model_dump()
    except Exception as e:
        logger.error(f"Auth error: {str(e)}")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def authenticate_api_key(request: Request, raw_key: str) -> dict:
    """
    Resolve a pc_live_/pc_test_ bearer token into the owner's user dict.

    401 for unknown/revoked/expired keys or when the owner no longer belongs to the
    key's workspace; 403 when the route is not key-callable or the key lacks its scope.
    """
    prefix = api_key_service.key_prefix(raw_key)
    route = request.scope.get("route")
    template = getattr(route, "path", None) or request.url.path

    def reject(status_code: int, detail: str, reason: str) -> HTTPException:
        record_audit("api_key.rejected", actor_type="system", resource_type="api_key", resource_id=prefix,
                     outcome="denied", reason=reason, metadata={"route": template, "method": request.method},
                     request=request)
        headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
        return HTTPException(status_code=status_code, detail=detail, headers=headers)

    key_state, row = api_key_service.resolve_api_key(raw_key)
    if key_state != "ok" or row is None:
        detail = f"API key is {key_state}." if key_state != "unknown" else "Invalid API key."
        raise reject(status.HTTP_401_UNAUTHORIZED, detail, key_state)

    scope_needed = api_key_service.required_scope(request.method, template)
    if scope_needed is None:
        raise reject(status.HTTP_403_FORBIDDEN, "This endpoint cannot be called with an API key.", "not_key_callable")
    if scope_needed not in (row.get("scopes") or []):
        raise reject(status.HTTP_403_FORBIDDEN, f"API key lacks the '{scope_needed}' scope.", "missing_scope")

    membership = None
    if row.get("org_id"):
        from app.services import organizations as org_service
        if not org_service.orgs_enabled():
            raise reject(status.HTTP_401_UNAUTHORIZED, "Workspace keys are disabled on this deployment.", "orgs_disabled")
        membership = org_service.get_membership(str(row["org_id"]), str(row["user_id"]))
        if membership is None or not org_service.role_at_least(membership.get("role"), "member"):
            raise reject(status.HTTP_401_UNAUTHORIZED, "The key owner no longer has access to this workspace.",
                         "owner_not_member")

    api_key_service.touch_last_used(row)
    return api_key_service.build_auth_user(row, membership)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency that validates a Bearer token (Supabase JWT, or an API key when enabled)."""
    token = credentials.credentials
    if api_key_service.api_keys_enabled() and api_key_service.looks_like_api_key(token):
        user = authenticate_api_key(request, token)
    else:
        user = verify_supabase_token(token)
    # Lets middleware (usage metering) attribute the request without re-validating the token.
    request.state.auth_user = user
    return user


def get_websocket_token(websocket: WebSocket) -> str | None:
    """Extract a WebSocket token from query params, Authorization, or protocol."""
    query_token = websocket.query_params.get("token") or websocket.query_params.get("access_token")
    if query_token:
        return query_token

    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    protocol_header = websocket.headers.get("sec-websocket-protocol", "")
    for part in [p.strip() for p in protocol_header.split(",") if p.strip()]:
        if part.lower().startswith("bearer."):
            return part.split(".", 1)[1]

    return None


def get_current_websocket_user(websocket: WebSocket) -> dict:
    token = get_websocket_token(websocket)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing WebSocket token")
    return verify_supabase_token(token)
