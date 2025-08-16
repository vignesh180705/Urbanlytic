from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_submit_report():
    payload = {
        "user_id": "test123",
        "description": "Small fire in kitchen at downtown cafe",
        "location": "Chennai"
    }
    response = client.post("/submit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "incident_id" in data
    assert "incident" in data
    assert data["incident"]["category"] in ["Fire", "Other"]

def test_get_history():
    response = client.get("/history")
    assert response.status_code == 200
    data = response.json()
    assert "incidents" in data
    assert isinstance(data["incidents"], list)
