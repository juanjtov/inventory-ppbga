"""Tests for consolidated fiado accounts: GET /pending/today and POST /{id}/add-items."""
import uuid


# ── GET /pending/today ──


def test_get_pending_today_returns_list(client, auth_headers):
    """Endpoint returns a list (may or may not have items)."""
    res = client.get("/api/v1/sales/pending/today", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_get_pending_today_returns_todays_fiado(client, auth_headers, test_product_id):
    """A fiado sale created now should appear in today's pending list."""
    # Create a fiado sale
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "__test_today_fiado__",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]

    # Should appear in today's pending
    res = client.get("/api/v1/sales/pending/today", headers=auth_headers)
    assert res.status_code == 200
    ids = [s["id"] for s in res.json()]
    assert sale_id in ids

    # Verify fields
    sale = next(s for s in res.json() if s["id"] == sale_id)
    assert sale["client_name"] == "__test_today_fiado__"
    assert "total" in sale


def test_get_pending_today_excludes_paid(client, auth_headers, test_product_id):
    """A paid fiado sale should not appear in today's pending list."""
    # Create and pay
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "__test_paid_fiado__",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]

    pay_res = client.post(
        f"/api/v1/sales/{sale_id}/pay",
        json={"payment_method": "efectivo"},
        headers=auth_headers,
    )
    assert pay_res.status_code == 200

    # Should NOT appear
    res = client.get("/api/v1/sales/pending/today", headers=auth_headers)
    ids = [s["id"] for s in res.json()]
    assert sale_id not in ids


# ── POST /{id}/add-items ──


def test_add_items_to_pending_sale(client, auth_headers, test_product_id):
    """Add items to an existing pending fiado sale."""
    # Get initial stock
    prod = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    initial_stock = prod["stock"]

    # Create fiado sale with 1 item
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "__test_add_items__",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]
    original_total = create_res.json()["total"]

    # Add 2 more of the same product
    add_res = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": test_product_id, "quantity": 2}]},
        headers=auth_headers,
    )
    assert add_res.status_code == 200
    updated_sale = add_res.json()

    # Total should have increased
    assert updated_sale["total"] > original_total

    # Should now have 2 sale_items rows
    assert len(updated_sale["items"]) == 2

    # Stock should be decremented by 3 total (1 + 2)
    prod2 = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    assert prod2["stock"] == initial_stock - 3


def test_add_items_updates_total(client, auth_headers, test_product_id):
    """Total should be the sum of all items across additions."""
    # Get product price
    prod = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    price = prod["sale_price"]

    # Create fiado with qty 1
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "__test_total_calc__",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]
    assert create_res.json()["total"] == price * 1

    # Add qty 2
    add_res = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": test_product_id, "quantity": 2}]},
        headers=auth_headers,
    )
    assert add_res.status_code == 200
    assert add_res.json()["total"] == price * 3


def test_add_items_to_paid_sale_fails(client, auth_headers, test_product_id):
    """Cannot add items to a sale that has already been paid."""
    # Create and pay
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "__test_paid_add__",
        },
        headers=auth_headers,
    )
    sale_id = create_res.json()["id"]
    client.post(
        f"/api/v1/sales/{sale_id}/pay",
        json={"payment_method": "efectivo"},
        headers=auth_headers,
    )

    # Try to add items
    res = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": test_product_id, "quantity": 1}]},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "pendientes" in res.json()["detail"].lower()


def test_add_items_to_voided_sale_fails(client, auth_headers, test_product_id):
    """Cannot add items to a voided sale."""
    # Create and void
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "__test_voided_add__",
        },
        headers=auth_headers,
    )
    sale_id = create_res.json()["id"]
    client.post(
        f"/api/v1/sales/{sale_id}/void",
        json={"reason": "test void"},
        headers=auth_headers,
    )

    # Try to add items
    res = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": test_product_id, "quantity": 1}]},
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_add_items_to_nonexistent_sale_fails(client, auth_headers, test_product_id):
    """Adding items to a non-existent sale returns 404."""
    fake_id = str(uuid.uuid4())
    res = client.post(
        f"/api/v1/sales/{fake_id}/add-items",
        json={"items": [{"product_id": test_product_id, "quantity": 1}]},
        headers=auth_headers,
    )
    assert res.status_code == 404


def test_add_items_insufficient_stock(client, auth_headers, test_category_id, test_supplier_id):
    """Cannot add items when stock is insufficient."""
    # Create a product with stock=1
    prod_res = client.post(
        "/api/v1/products",
        json={
            "name": "__test_add_items_stock__",
            "category_id": test_category_id,
            "supplier_id": test_supplier_id,
            "sale_price": 1000,
            "stock": 2,
            "type": "product",
        },
        headers=auth_headers,
    )
    if prod_res.status_code != 200:
        return  # skip if product already exists
    product_id = prod_res.json()["id"]

    # Create fiado sale with qty 1
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "__test_stock_add__",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]

    # Try to add qty 999 — should fail
    res = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": product_id, "quantity": 999}]},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "insuficiente" in res.json()["detail"].lower()


def test_void_consolidated_sale_restores_all_stock(client, auth_headers, test_product_id):
    """Voiding a consolidated sale restores stock from all additions."""
    # Get initial stock
    prod = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    stock_before = prod["stock"]

    # Create fiado with qty 1
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "__test_void_consol__",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]

    # Add 2 more items
    add_res = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": test_product_id, "quantity": 2}]},
        headers=auth_headers,
    )
    assert add_res.status_code == 200

    # Verify stock went down by 3
    prod2 = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    assert prod2["stock"] == stock_before - 3

    # Void the sale
    void_res = client.post(
        f"/api/v1/sales/{sale_id}/void",
        json={"reason": "test void consolidated"},
        headers=auth_headers,
    )
    assert void_res.status_code == 200

    # Stock should be fully restored
    prod3 = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    assert prod3["stock"] == stock_before


def test_add_items_service_no_stock_check(client, auth_headers, test_service_id):
    """Services can be added without stock checks."""
    # Create fiado sale with a service
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_service_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "__test_service_add__",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]

    # Add more services
    add_res = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": test_service_id, "quantity": 3}]},
        headers=auth_headers,
    )
    assert add_res.status_code == 200
    assert len(add_res.json()["items"]) == 2
