"""Auth endpoint tests."""


def test_login_success(client, test_owner_credentials):
    res = client.post("/api/v1/auth/login", json=test_owner_credentials)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "user" in data
    assert data["user"]["role"] == "owner"


def test_login_wrong_password(client, test_owner_credentials):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": test_owner_credentials["email"], "password": "wrongpassword"},
    )
    assert res.status_code == 401


def test_login_nonexistent_email(client):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "whatever"},
    )
    assert res.status_code == 401


def test_me(client, auth_headers):
    res = client.get("/api/v1/auth/me", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "email" in data
    assert "role" in data
    assert "full_name" in data


def test_me_no_auth(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code in (401, 403)
