import pytest #type: ignore
from unittest.mock import patch
from app import app
from datetime import timedelta

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "testkey"
    return app.test_client()

@patch("services.user_service.UserService.authenticate_user")
def test_login_success(mock_auth, client):
    # Mocking successful authentication
    mock_auth.return_value = ({"username": "testuser"}, None)

    data = {
        "username": "testuser",
        "password": "password123",
        "remember": "on"
    }

    # Use form-encoded data because request.form expects it
    response = client.post("/login", data=data, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with client.session_transaction() as sess:
        assert sess["user"] == "testuser"
        assert sess.permanent is True

@patch("services.user_service.UserService.authenticate_user")
def test_login_failure(mock_auth, client):
    # Mocking failed authentication
    mock_auth.return_value = (None, "Invalid credentials")

    data = {"username": "wronguser", "password": "wrongpass"}

    response = client.post("/login", data=data)

    assert response.status_code == 200
    assert b"Invalid credentials" in response.data
