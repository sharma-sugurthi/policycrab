import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

# Create a test client
client = TestClient(app)

from app.api.auth import get_current_user

@pytest.fixture
def mock_auth():
    # Mock the get_current_user dependency using FastAPI's dependency_overrides
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-id"}
    yield
    # Clean up after test
    app.dependency_overrides.pop(get_current_user, None)

def test_audit_upload_rejects_invalid_document_type(mock_auth):
    """
    Ensures that if the multimodal LLM visually identifies the uploaded document
    as something other than a 'bill' or 'eob' (e.g., 'prescription', 'policy'),
    the route properly returns a 400 Bad Request to fail fast.
    """
    
    # Mock the EOB extractor to simulate an invalid document type
    mock_result = {
        "document_type": "prescription",
        "service_lines": []
    }
    
    with patch("app.api.audit_routes.extract_eob_safely", return_value=mock_result):
        # We simulate uploading a valid PDF byte string, but the mocked LLM will say it's a prescription.
        files = {"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}
        response = client.post("/api/audit/upload", files=files)
        
        # It should return a 400 error due to document type validation
        assert response.status_code == 400
        # Check that the specific 'visually identified' error message is returned
        assert "visually identified as 'prescription'" in response.json()["detail"]
        assert "Please upload a valid medical bill or EOB" in response.json()["detail"]

def test_audit_upload_accepts_valid_document_type(mock_auth):
    """
    Ensures that if the document is a valid 'bill' or 'eob' and contains service lines,
    it processes correctly.
    """
    
    mock_result = {
        "document_type": "bill",
        "service_lines": [{"cpt_code": "99213", "billed_amount": 150.0}]
    }
    
    from unittest.mock import AsyncMock
    mock_audit_result = MagicMock()
    mock_audit_result.model_dump.return_value = {"overall_risk": "low", "flags": [], "potential_savings": 0}
    mock_audit_result.overall_risk = "low"
    mock_audit_result.total_billed = 150.0
    mock_audit_result.potential_savings = 0
    
    with patch("app.api.audit_routes.extract_eob_safely", return_value=mock_result), \
         patch("app.api.audit_routes.run_bill_audit", new_callable=AsyncMock, return_value=mock_audit_result), \
         patch("app.api.audit_routes.create_user_audit"): # Mock DB call
        
        files = {"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}
        response = client.post("/api/audit/upload", files=files)
        
        assert response.status_code == 200
        assert response.json()["success"] == True
        assert response.json()["audit_result"]["overall_risk"] == "low"
