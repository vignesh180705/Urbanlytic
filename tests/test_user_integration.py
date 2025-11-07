import pytest #type: ignore
from unittest.mock import patch, MagicMock
from app import app

@pytest.fixture
def client():
    app.testing = True
    with app.test_client() as client:
        yield client

@patch("repository.incident_repo.IncidentRepository.get_all_reports")
def test_get_all_reports(mock_get_reports, client):
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {
        "description": "Garbage overflow near park",
        "location": "Central Park",
        "category": "Waste Management",
        "timestamp": "2025-11-07T12:00:00",
        "priority": "High",
        "status": "Pending"
    }
    mock_get_reports.return_value = [mock_doc]  

    with client.session_transaction() as sess:
        sess["user"] = {"username": "testuser"}

    response = client.get("/user/all_reports")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "reports" in data
    assert isinstance(data["reports"], list)
    assert len(data["reports"]) > 0
    assert data["reports"][0]["category"] == "Waste Management"
