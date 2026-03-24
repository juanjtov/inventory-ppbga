"""Inventory endpoint tests."""


def test_inventory_entry(client, auth_headers, test_product_id, test_supplier_id):
    """Inventory entry increments stock."""
    # Get current stock
    prod = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    initial_stock = prod["stock"]

    res = client.post(
        "/api/v1/inventory/entry",
        json={
            "product_id": test_product_id,
            "quantity": 10,
            "supplier_id": test_supplier_id,
            "price_confirmed": True,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200

    # Verify stock increased
    prod2 = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    assert prod2["stock"] == initial_stock + 10


def test_inventory_entry_price_change(client, auth_headers, test_product_id, test_supplier_id):
    """Inventory entry with price not confirmed updates purchase_price."""
    res = client.post(
        "/api/v1/inventory/entry",
        json={
            "product_id": test_product_id,
            "quantity": 5,
            "supplier_id": test_supplier_id,
            "price_confirmed": False,
            "actual_price": 9999,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200

    # Verify purchase_price updated
    prod = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    assert prod["purchase_price"] == 9999


def test_internal_use(client, auth_headers, test_product_id):
    """Internal use decrements stock."""
    prod = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    initial_stock = prod["stock"]

    res = client.post(
        "/api/v1/inventory/internal-use",
        json={
            "product_id": test_product_id,
            "quantity": 2,
            "reason": "Uso de prueba para testing",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200

    prod2 = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    assert prod2["stock"] == initial_stock - 2


def test_internal_use_exceeds_stock(client, auth_headers, test_category_id, test_supplier_id):
    """Cannot use more than available stock."""
    # Create product with stock=1
    prod_res = client.post(
        "/api/v1/products",
        json={
            "name": "__test_internal_use_exceed__",
            "category_id": test_category_id,
            "supplier_id": test_supplier_id,
            "sale_price": 1000,
            "stock": 1,
            "type": "product",
        },
        headers=auth_headers,
    )
    if prod_res.status_code != 200:
        return
    product_id = prod_res.json()["id"]

    res = client.post(
        "/api/v1/inventory/internal-use",
        json={
            "product_id": product_id,
            "quantity": 999,
            "reason": "Intentando usar mas del stock disponible",
        },
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_internal_use_service_rejected(client, auth_headers, test_service_id):
    """Cannot register internal use for a service."""
    res = client.post(
        "/api/v1/inventory/internal-use",
        json={
            "product_id": test_service_id,
            "quantity": 1,
            "reason": "Esto deberia fallar para servicios",
        },
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_internal_use_short_reason(client, auth_headers, test_product_id):
    """Reason must be at least 5 characters."""
    res = client.post(
        "/api/v1/inventory/internal-use",
        json={
            "product_id": test_product_id,
            "quantity": 1,
            "reason": "abc",
        },
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_movements(client, auth_headers, test_product_id):
    """Get product movements timeline."""
    res = client.get(
        "/api/v1/inventory/movements",
        params={"product_id": test_product_id},
        headers=auth_headers,
    )
    assert res.status_code == 200
    movements = res.json()
    assert isinstance(movements, list)
    if movements:
        m = movements[0]
        assert "type" in m
        assert "quantity" in m
        assert "date" in m
        assert m["type"] in ("sale", "entry", "internal_use", "void")
