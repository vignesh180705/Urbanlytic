import pytest #type: ignore
from unittest.mock import patch
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()

@patch("services.report_service.publisher.publish")  
@patch("services.report_service.AIService.classify_incident") 
@patch("repository.incident_repo.IncidentRepository.get_report_by_id")
@patch("repository.incident_repo.IncidentRepository.save")
def test_report_submission(mock_save, mock_get, mock_ai, mock_pub, client):
    mock_save.return_value = "test_incident_id"
    mock_get.return_value = {
        "id": "test_incident_id",
        "location": "123 Main St",
        "description": "Overflowing garbage bin",
        "category": "Waste Management",
        "priority": "Low",
        "summary": "Garbage overflow near main road"
    }
    mock_ai.return_value = {
        "category": "Waste Management",
        "priority": "Low",
        "summary": "Garbage overflow near main road"
    }
    mock_pub.return_value = True
    with client.session_transaction() as sess:
        sess["user"] = {"username": "testuser", "email": "test@example.com"}

    data = {
        "location": "123 Main St",
        "type": "Waste Management",
        "description": "Overflowing garbage bin"
    }

    response = client.post("/submit", data=data)

    assert response.status_code == 200
    resp_json = response.get_json()
    assert resp_json["status"] == "success"
    assert "incident_id" in resp_json
    assert "report" in resp_json
