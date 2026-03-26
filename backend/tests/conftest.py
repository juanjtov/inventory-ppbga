import pytest
import httpx
import os
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the FastAPI app under test."""
    return "http://localhost:8000"


@pytest.fixture(scope="session")
def supabase_client():
    """Direct Supabase client for test setup/teardown."""
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    return create_client(url, key)


@pytest.fixture(scope="session")
def test_owner_credentials():
    """Owner credentials for testing. Must be set up in Supabase beforehand."""
    return {
        "email": os.environ.get("TEST_OWNER_EMAIL", "owner@test.premierpadel.com"),
        "password": os.environ.get("TEST_OWNER_PASSWORD", "TestOwner123!"),
    }


@pytest.fixture(scope="session")
def owner_token(base_url, test_owner_credentials):
    """Get an access token for the owner user."""
    with httpx.Client(base_url=base_url) as client:
        res = client.post("/api/v1/auth/login", json=test_owner_credentials)
        assert res.status_code == 200, f"Owner login failed: {res.text}"
        return res.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(owner_token):
    """Auth headers for owner user."""
    return {"Authorization": f"Bearer {owner_token}"}


@pytest.fixture(scope="session")
def client(base_url):
    """HTTPX client pointing at the running API."""
    with httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True) as c:
        yield c


# ── Test data cleanup helpers ──


@pytest.fixture(scope="session")
def test_category_id(client, auth_headers):
    """Create a test category and return its ID."""
    res = client.post(
        "/api/v1/categories",
        json={"name": "__test_category__"},
        headers=auth_headers,
    )
    if res.status_code == 200:
        return res.json()["id"]
    # May already exist
    res2 = client.get("/api/v1/categories", headers=auth_headers)
    for c in res2.json():
        if c["name"] == "__test_category__":
            return c["id"]
    raise Exception("Could not create test category")


@pytest.fixture(scope="session")
def test_supplier_id(client, auth_headers):
    """Create a test supplier and return its ID."""
    res = client.post(
        "/api/v1/suppliers",
        json={"name": "__test_supplier__"},
        headers=auth_headers,
    )
    if res.status_code == 200:
        return res.json()["id"]
    res2 = client.get("/api/v1/suppliers", headers=auth_headers)
    for s in res2.json():
        if s["name"] == "__test_supplier__":
            return s["id"]
    raise Exception("Could not create test supplier")


@pytest.fixture(scope="session")
def test_product_id(client, auth_headers, test_category_id, test_supplier_id):
    """Create a test product and return its ID."""
    res = client.post(
        "/api/v1/products",
        json={
            "name": "__test_product__",
            "category_id": test_category_id,
            "supplier_id": test_supplier_id,
            "sale_price": 5000,
            "purchase_price": 3000,
            "stock": 100,
            "type": "product",
        },
        headers=auth_headers,
    )
    if res.status_code == 200:
        return res.json()["id"]
    # Product may already exist — fetch it
    res2 = client.get("/api/v1/products", headers=auth_headers)
    for p in res2.json():
        if p["name"] == "__test_product__":
            return p["id"]
    raise Exception(f"Could not create test product: {res.text}")


@pytest.fixture(scope="session")
def test_service_id(client, auth_headers, test_category_id, test_supplier_id):
    """Create a test service and return its ID."""
    res = client.post(
        "/api/v1/products",
        json={
            "name": "__test_service__",
            "category_id": test_category_id,
            "supplier_id": test_supplier_id,
            "sale_price": 10000,
            "type": "service",
        },
        headers=auth_headers,
    )
    if res.status_code == 200:
        return res.json()["id"]
    res2 = client.get("/api/v1/products", headers=auth_headers)
    for p in res2.json():
        if p["name"] == "__test_service__":
            return p["id"]
    raise Exception(f"Could not create test service: {res.text}")
