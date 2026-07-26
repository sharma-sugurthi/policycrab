from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
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


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """FastAPI dependency that validates a Bearer token."""
    return verify_supabase_token(credentials.credentials)


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
