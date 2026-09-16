"""Pydantic models for API keys."""

from pydantic import BaseModel, Field, field_validator

ENVIRONMENTS = ("live", "test")


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    scopes: list[str] = Field(..., min_length=1, max_length=32)
    environment: str = "live"
    expires_in_days: int | None = Field(None, ge=1, le=365)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Give the key a name.")
        return v

    @field_validator("environment")
    @classmethod
    def _env(cls, v: str) -> str:
        v = (v or "live").strip().lower()
        if v not in ENVIRONMENTS:
            raise ValueError("environment must be 'live' or 'test'")
        return v

    @field_validator("scopes")
    @classmethod
    def _scopes(cls, v: list[str]) -> list[str]:
        cleaned = sorted({s.strip().lower() for s in v if s and s.strip()})
        if not cleaned:
            raise ValueError("Select at least one scope.")
        return cleaned


class ApiKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: list[str] = []
    environment: str = "live"
    user_id: str
    owner_email: str | None = None
    org_id: str | None = None
    last_used_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    created_at: str | None = None
    active: bool = True


class ApiKeyCreated(BaseModel):
    key: str = Field(..., description="The full API key. Shown exactly once; store it now.")
    api_key: ApiKeyOut


class ApiKeysStatus(BaseModel):
    enabled: bool
    scopes: dict[str, str] = {}
