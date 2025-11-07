import pytest #type: ignore
from unittest.mock import patch, MagicMock
from app import app
import io

@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()

@patch("repository.incident_repo.IncidentRepository.update_report_status")
def test_update_report_status(mock_update, client):
    mock_update.return_value = True

    with client.session_transaction() as sess:
        sess["user"] = {"username": "admin"}

    data = {
        "status": "Resolved",
        "proof": (io.BytesIO(b"fake image content"), "proof.jpg")
    }

    response = client.post(
        "/admin/reports/test_incident/update",
        data=data,
        content_type="multipart/form-data"
    )

    assert response.status_code in [302, 200]
    mock_update.assert_called_once_with("test_incident", "Resolved", 
                                        "/static/uploads/proofs/proof.jpg")

@patch("repository.incident_repo.IncidentRepository.update_report_status")
def test_update_report_status_without_proof(mock_update, client):
    with client.session_transaction() as sess:
        sess["user"] = {"username": "admin"}

    data = {"status": "Resolved"}  

    response = client.post("/admin/reports/test_incident/update", data=data)

    assert response.status_code == 400
    assert b"Proof image required" in response.data
