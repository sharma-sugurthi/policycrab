"""
Tests for Smart Email Routing and Public AI Crawler Endpoints
"""
import pytest
from app.services.carrier_email_resolver import resolve_carrier_email, get_state_doi

def test_resolve_carrier_email_direct_match():
    profile = resolve_carrier_email("Blue Cross Blue Shield")
    assert profile.confidence == "HIGH"
    assert profile.appeals_email == "appeals@bcbs.com"

def test_resolve_carrier_email_fuzzy_match():
    # 'bcbs' maps to 'blue cross blue shield'
    profile = resolve_carrier_email("bcbs")
    assert profile.confidence == "HIGH"
    assert profile.appeals_email == "appeals@bcbs.com"
    
    # partial match
    profile = resolve_carrier_email("United Healthcare of Texas")
    # 'united healthcare' should match
    assert profile.confidence == "MEDIUM"
    assert profile.appeals_email == "appeals@uhc.com"

def test_resolve_carrier_email_no_match():
    profile = resolve_carrier_email("Acme Unknown Insurance")
    assert profile.confidence == "LOW"
    assert profile.appeals_email is None

def test_get_state_doi():
    doi = get_state_doi("CA")
    assert "California" in doi["name"]
    assert "insurance.ca.gov" in doi["email"]

    doi_default = get_state_doi("XX")
    assert "CMS" in doi_default["name"]

# Fastapi test client for routes
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_public_about_route():
    response = client.get("/api/public/about")
    assert response.status_code == 200
    data = response.json()
    assert data["product"] == "PolicyCrab"
    assert "model" in data

def test_public_faqs_route():
    response = client.get("/api/public/faqs")
    assert response.status_code == 200
    data = response.json()
    assert "faqs" in data
    assert len(data["faqs"]) > 0

def test_public_capabilities_route():
    response = client.get("/api/public/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "claim_categories" in data
    assert "regulatory_frameworks" in data

# Note: /api/email/* routes are authenticated, so testing them requires auth headers
# But we can test the unauthenticated rejection
def test_smart_suggest_requires_auth():
    # Clear any global overrides (e.g. from test_chunking.py) to ensure auth is actually checked
    app.dependency_overrides.clear()
    
    response = client.post("/api/email/smart-suggest", json={
        "carrier_name": "Aetna",
        "state": "TX"
    })
    # Should be 401 Unauthorized because it's behind Depends(get_current_user)
    assert response.status_code == 401
