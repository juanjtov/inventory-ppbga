"""Users endpoint tests."""


def test_list_users(client, auth_headers):
    res = client.get("/api/v1/users", headers=auth_headers)
    assert res.status_code == 200
    users = res.json()
    assert isinstance(users, list)
    assert len(users) >= 1  # At least the owner


def test_create_user(client, auth_headers):
    """Create a worker user (may already exist)."""
    import time
    unique = int(time.time())
    res = client.post(
        "/api/v1/users",
        json={
            "email": f"test_worker_{unique}@test.premierpadel.com",
            "password": "TestWorker123!",
            "full_name": f"Test Worker {unique}",
            "role": "worker",
        },
        headers=auth_headers,
    )
    # 200 if created, 400 if email exists
    assert res.status_code in (200, 400)
    if res.status_code == 200:
        data = res.json()
        assert data["role"] == "worker"


def test_cannot_create_owner(client, auth_headers):
    """Cannot create another owner user."""
    import time
    unique = int(time.time())
    res = client.post(
        "/api/v1/users",
        json={
            "email": f"test_owner_{unique}@test.premierpadel.com",
            "password": "TestOwner123!",
            "full_name": "Test Owner",
            "role": "owner",
        },
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_audit_log(client, auth_headers):
    """Audit log should return entries."""
    res = client.get("/api/v1/audit-log", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)
