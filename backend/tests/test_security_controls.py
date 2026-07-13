"""Tests for lightweight API abuse controls."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.auth import get_websocket_token
from app.security import rate_limit as limiter
from app.security.rate_limit import RateLimitRule, check_rate_limit, request_identity, websocket_identity


def setup_function():
    limiter._buckets.clear()


def test_check_rate_limit_blocks_after_configured_budget():
    rule = RateLimitRule(scope="test", max_requests=2, window_seconds=60)

    check_rate_limit("user:abc", rule)
    check_rate_limit("user:abc", rule)

    with pytest.raises(HTTPException) as exc:
        check_rate_limit("user:abc", rule)

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"]


def test_rate_limit_scopes_are_independent():
    check_rate_limit("user:abc", RateLimitRule(scope="one", max_requests=1, window_seconds=60))

    check_rate_limit("user:abc", RateLimitRule(scope="two", max_requests=1, window_seconds=60))

    with pytest.raises(HTTPException):
        check_rate_limit("user:abc", RateLimitRule(scope="one", max_requests=1, window_seconds=60))


def test_request_identity_prefers_bearer_token_without_storing_it():
    request = SimpleNamespace(
        headers={"authorization": "Bearer secret-token"},
        client=SimpleNamespace(host="203.0.113.10"),
    )

    identity = request_identity(request)

    assert identity.startswith("token:")
    assert "secret-token" not in identity


def test_request_identity_uses_forwarded_ip_without_token():
    request = SimpleNamespace(
        headers={"x-forwarded-for": "198.51.100.4, 10.0.0.1"},
        client=SimpleNamespace(host="203.0.113.10"),
    )

    assert request_identity(request) == "ip:198.51.100.4"


def test_websocket_token_from_query_param():
    websocket = Mock(query_params={"token": "query-token"}, headers={})

    assert get_websocket_token(websocket) == "query-token"


def test_websocket_token_from_bearer_protocol():
    websocket = Mock(
        query_params={},
        headers={"sec-websocket-protocol": "policycrab, bearer.protocol-token"},
    )

    assert get_websocket_token(websocket) == "protocol-token"


def test_websocket_identity_does_not_expose_user_id():
    identity = websocket_identity({"id": "user-123"})

    assert identity.startswith("user:")
    assert "user-123" not in identity
