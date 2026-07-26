"""Tests for lightweight API abuse controls."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.auth import get_websocket_token, verify_supabase_token
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


def test_benchmark_token_disabled_by_default(monkeypatch):
    from app.api import auth

    monkeypatch.setattr(auth.settings, "debug", False)
    monkeypatch.setattr(auth.settings, "allow_benchmark_auth", False)

    with pytest.raises(HTTPException) as exc:
        verify_supabase_token("BENCHMARK_TOKEN")

    assert exc.value.status_code == 401
    assert exc.value.detail == "Benchmark authentication is disabled"


def test_benchmark_token_requires_explicit_non_production_gate(monkeypatch):
    from app.api import auth

    monkeypatch.setattr(auth.settings, "debug", False)
    monkeypatch.setattr(auth.settings, "allow_benchmark_auth", True)

    # The bypass emits auth.BENCHMARK_USER_ID (a stable UUIDv4-shaped string),
    # not the literal "benchmark_user" — Supabase `user_id` columns are typed as
    # uuid and reject ad-hoc strings with 22P02. See app/api/auth.py:11.
    assert verify_supabase_token("BENCHMARK_TOKEN")["id"] == auth.BENCHMARK_USER_ID


def test_document_scrubber_redacts_structured_identifiers():
    from app.security import presidio_scrubber

    presidio_scrubber._scrubber = None
    clean, count = presidio_scrubber.scrub_phi(
        "Patient: Test Patient Member ID: TST123456789 "
        "Phone: 555-123-4567 SSN: 123-45-6789 "
        "Card: 4111 1111 1111 1111"
    )

    assert count >= 4
    assert "TST123456789" not in clean
    assert "555-123-4567" not in clean
    assert "123-45-6789" not in clean
    assert "4111 1111 1111 1111" not in clean


def test_document_scrubber_fails_closed_when_presidio_crashes(monkeypatch):
    from app.security import presidio_scrubber

    scrubber = presidio_scrubber.HIPAADocumentScrubber.__new__(
        presidio_scrubber.HIPAADocumentScrubber
    )
    scrubber._available = True
    scrubber.entities_to_redact = ["PHONE_NUMBER"]

    class BrokenAnalyzer:
        def analyze(self, **kwargs):
            raise RuntimeError("simulated analyzer failure")

    scrubber.analyzer = BrokenAnalyzer()
    scrubber.anonymizer = object()

    monkeypatch.setattr(presidio_scrubber, "_scrubber", scrubber)

    with pytest.raises(presidio_scrubber.PHIScrubbingError):
        presidio_scrubber.scrub_phi("Patient phone: 555-123-4567")
