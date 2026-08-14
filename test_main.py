import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app, CLIENT_API_KEY


client = TestClient(app)

def test_missing_api_key_returns_401():
    """Test that a request without the X-API-Key header is rejected."""
    payload = {
        "text": "The patient presented with a fever.",
        "extraction_schema": {"symptoms": "string"}
    }
    response = client.post("/api/extract-async", json=payload)
    
    assert response.status_code == 401
    assert "Missing API Key" in response.json()["detail"]

@patch('main.process_extraction_task') # Mocks the background task
def test_valid_request_returns_202_and_task_id(mock_task):
    """Test that a valid request is accepted and returns a task_id."""
    headers = {"X-API-Key": CLIENT_API_KEY}
    payload = {
        "text": "The patient is 45 years old.",
        "extraction_schema": {"age": "integer"}
    }
    
    response = client.post("/api/extract-async", headers=headers, json=payload)
    
    assert response.status_code == 202
    data = response.json()
    
    assert "task_id" in data
    assert data["status"] == "pending"

    mock_task.assert_called_once()