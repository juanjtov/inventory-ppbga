"""Sales endpoint tests."""
import time


def test_create_sale_cash(client, auth_headers, test_product_id):
    """Create a cash sale and verify stock decrements."""
    # Get initial stock
    prod = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    initial_stock = prod["stock"]

    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 2}],
            "payment_method": "efectivo",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    sale = res.json()
    assert sale["status"] == "completed"
    assert sale["payment_method"] == "efectivo"
    assert sale["total"] > 0
    assert len(sale["items"]) == 1
    assert sale["items"][0]["quantity"] == 2

    # Verify stock decremented
    prod2 = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    assert prod2["stock"] == initial_stock - 2


def test_create_sale_service(client, auth_headers, test_service_id):
    """Services can be sold without stock checks."""
    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_service_id, "quantity": 1}],
            "payment_method": "efectivo",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200


def test_create_sale_fiado_requires_client(client, auth_headers, test_product_id):
    """Fiado sales require client_name."""
    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
        },
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_create_sale_fiado_with_client(client, auth_headers, test_product_id):
    """Fiado sale with client name creates pending sale."""
    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "Juan Test",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    sale = res.json()
    assert sale["status"] == "pending"
    assert sale["client_name"] == "Juan Test"
    return sale["id"]


def test_list_pending_sales(client, auth_headers):
    res = client.get("/api/v1/sales/pending", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_pay_pending_sale(client, auth_headers, test_product_id):
    """Create fiado sale, then mark as paid."""
    # Create fiado sale
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "Pay Test Client",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]

    # Pay it
    pay_res = client.post(
        f"/api/v1/sales/{sale_id}/pay",
        json={"payment_method": "efectivo"},
        headers=auth_headers,
    )
    assert pay_res.status_code == 200
    assert pay_res.json()["status"] == "completed"


def test_void_sale(client, auth_headers, test_product_id):
    """Void a sale and verify stock is restored."""
    # Get stock before
    prod = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    stock_before = prod["stock"]

    # Create sale
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 3}],
            "payment_method": "efectivo",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]

    # Verify stock reduced
    prod2 = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    assert prod2["stock"] == stock_before - 3

    # Void it
    void_res = client.post(
        f"/api/v1/sales/{sale_id}/void",
        json={"reason": "Test void"},
        headers=auth_headers,
    )
    assert void_res.status_code == 200
    assert void_res.json()["status"] == "voided"

    # Verify stock restored
    prod3 = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
    assert prod3["stock"] == stock_before


def test_void_already_voided(client, auth_headers, test_product_id):
    """Cannot void an already voided sale."""
    # Create and void
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "efectivo",
        },
        headers=auth_headers,
    )
    sale_id = create_res.json()["id"]
    client.post(f"/api/v1/sales/{sale_id}/void", json={"reason": "first void"}, headers=auth_headers)

    # Try to void again
    res = client.post(
        f"/api/v1/sales/{sale_id}/void",
        json={"reason": "second void"},
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_list_sales(client, auth_headers):
    res = client.get("/api/v1/sales", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_list_sales_with_filters(client, auth_headers):
    from datetime import date
    today = date.today().isoformat()
    res = client.get(
        "/api/v1/sales",
        params={"date_from": today, "date_to": today, "status": "completed"},
        headers=auth_headers,
    )
    assert res.status_code == 200


def test_get_sale_detail(client, auth_headers, test_product_id):
    # Create a sale first
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "efectivo",
        },
        headers=auth_headers,
    )
    sale_id = create_res.json()["id"]

    res = client.get(f"/api/v1/sales/{sale_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 1


def test_sales_summary_basic(client, auth_headers):
    """/sales/summary returns the four cards, regardless of result count."""
    from datetime import date

    today = date.today().isoformat()
    res = client.get(
        "/api/v1/sales/summary",
        params={"date_from": today, "date_to": today},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert set(data.keys()) == {
        "total_count",
        "total_amount",
        "voided_count",
        "fiado_pending",
    }
    assert data["total_amount"] >= 0


def test_sales_summary_beyond_page_size(
    client, auth_headers, test_product_id
):
    """Summary counts and totals cover ALL matching sales, not just the
    first 20 that /sales returns on a single page."""
    from datetime import date

    today = date.today().isoformat()
    marker_client = f"__test_summary_{int(time.time())}__"

    baseline = client.get(
        "/api/v1/sales/summary",
        params={"date_from": today, "date_to": today},
        headers=auth_headers,
    ).json()

    # Create 25 small sales so we exceed the /sales default page of 20
    sale_ids = []
    try:
        for _ in range(25):
            res = client.post(
                "/api/v1/sales",
                json={
                    "items": [{"product_id": test_product_id, "quantity": 1}],
                    "payment_method": "efectivo",
                    "notes": marker_client,
                },
                headers=auth_headers,
            )
            assert res.status_code == 200, res.text
            sale_ids.append(res.json()["id"])

        after = client.get(
            "/api/v1/sales/summary",
            params={"date_from": today, "date_to": today},
            headers=auth_headers,
        ).json()
        assert after["total_count"] >= baseline["total_count"] + 25
        assert after["total_amount"] >= baseline["total_amount"] + 25 * 1  # prices > 0
    finally:
        for sid in sale_ids:
            client.post(
                f"/api/v1/sales/{sid}/void",
                json={"reason": marker_client},
                headers=auth_headers,
            )


def test_sales_summary_respects_filters(client, auth_headers, test_product_id):
    """status=voided returns only voided totals."""
    from datetime import date

    today = date.today().isoformat()
    marker = f"__test_summary_filt_{int(time.time())}__"

    # Create + void a sale
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "efectivo",
            "notes": marker,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200, create_res.text
    sale_id = create_res.json()["id"]
    client.post(
        f"/api/v1/sales/{sale_id}/void",
        json={"reason": marker},
        headers=auth_headers,
    )

    voided_summary = client.get(
        "/api/v1/sales/summary",
        params={"date_from": today, "date_to": today, "status": "voided"},
        headers=auth_headers,
    ).json()
    # total_amount excludes voided sales by semantic, so it can be 0 even though
    # total_count > 0 when only voided sales match
    assert voided_summary["voided_count"] >= 1
    assert voided_summary["total_amount"] == 0


def test_cannot_oversell(client, auth_headers, test_category_id, test_supplier_id):
    """Cannot sell more than available stock."""
    # Create a product with stock=1
    prod_res = client.post(
        "/api/v1/products",
        json={
            "name": "__test_oversell__",
            "category_id": test_category_id,
            "supplier_id": test_supplier_id,
            "sale_price": 1000,
            "stock": 1,
            "type": "product",
        },
        headers=auth_headers,
    )
    if prod_res.status_code != 200:
        return  # skip if product already exists
    product_id = prod_res.json()["id"]

    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": product_id, "quantity": 999}],
            "payment_method": "efectivo",
        },
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "insuficiente" in res.json()["detail"].lower()
