"""Categories and Suppliers tests."""


def test_list_categories(client, auth_headers):
    res = client.get("/api/v1/categories", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_create_category(client, auth_headers):
    res = client.post(
        "/api/v1/categories",
        json={"name": "__test_cat_unique__"},
        headers=auth_headers,
    )
    # Either 200 (created) or 400/409 (already exists)
    assert res.status_code in (200, 400, 409)


def test_list_suppliers(client, auth_headers):
    res = client.get("/api/v1/suppliers", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_create_supplier(client, auth_headers):
    res = client.post(
        "/api/v1/suppliers",
        json={"name": "__test_sup_unique__"},
        headers=auth_headers,
    )
    assert res.status_code in (200, 400, 409)
