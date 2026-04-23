"""Stock adjustment (physical count) endpoint tests."""
import time


def _make_product(client, auth_headers, category_id, supplier_id, marker: str, stock: int = 10):
    res = client.post(
        "/api/v1/products",
        json={
            "name": marker,
            "category_id": category_id,
            "supplier_id": supplier_id,
            "sale_price": 1000,
            "stock": stock,
            "type": "product",
        },
        headers=auth_headers,
    )
    if res.status_code != 200:
        # Product may already exist
        lst = client.get("/api/v1/products", headers=auth_headers).json()
        for p in lst:
            if p["name"] == marker:
                return p["id"]
        raise Exception(f"Could not create test product: {res.text}")
    return res.json()["id"]


def test_create_adjustment_updates_stock(
    client, auth_headers, test_category_id, test_supplier_id
):
    marker = f"__test_adj_stock_{int(time.time())}__"
    pid = _make_product(client, auth_headers, test_category_id, test_supplier_id, marker, stock=10)

    res = client.post(
        "/api/v1/stock-adjustments",
        json={
            "product_id": pid,
            "counted_quantity": 8,
            "reason": "Conteo semanal de prueba",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    adj = res.json()
    assert adj["system_quantity"] == 10
    assert adj["counted_quantity"] == 8
    assert adj["difference"] == -2

    # Product stock now matches counted
    prod = client.get(f"/api/v1/products/{pid}", headers=auth_headers).json()
    assert prod["stock"] == 8


def test_adjustment_writes_audit_log(
    client, auth_headers, test_category_id, test_supplier_id
):
    marker = f"__test_adj_audit_{int(time.time())}__"
    pid = _make_product(client, auth_headers, test_category_id, test_supplier_id, marker, stock=5)

    client.post(
        "/api/v1/stock-adjustments",
        json={"product_id": pid, "counted_quantity": 7, "reason": marker},
        headers=auth_headers,
    )

    # Audit log: entity_type=product, entity_id=pid should have a stock_adjustment row
    log = client.get(
        "/api/v1/audit-log",
        params={"entity_type": "product", "entity_id": pid, "limit": 10},
        headers=auth_headers,
    ).json()
    matching = [r for r in log if r["action"] == "stock_adjustment"]
    assert len(matching) >= 1
    top = matching[0]
    assert top["old_values"]["stock"] == 5
    assert top["new_values"]["stock"] == 7
    assert top["new_values"]["difference"] == 2


def test_adjustment_rejects_negative(
    client, auth_headers, test_category_id, test_supplier_id
):
    marker = f"__test_adj_neg_{int(time.time())}__"
    pid = _make_product(client, auth_headers, test_category_id, test_supplier_id, marker, stock=3)

    res = client.post(
        "/api/v1/stock-adjustments",
        json={"product_id": pid, "counted_quantity": -1},
        headers=auth_headers,
    )
    # CHECK constraint (server-side) or early validation — either way, 4xx
    assert res.status_code in (400, 422), res.text


def test_adjustment_list_filters_by_product(
    client, auth_headers, test_category_id, test_supplier_id
):
    marker = f"__test_adj_list_{int(time.time())}__"
    pid = _make_product(client, auth_headers, test_category_id, test_supplier_id, marker, stock=5)

    client.post(
        "/api/v1/stock-adjustments",
        json={"product_id": pid, "counted_quantity": 5, "reason": f"{marker}_zero"},
        headers=auth_headers,
    )

    res = client.get(
        "/api/v1/stock-adjustments",
        params={"product_id": pid, "limit": 20},
        headers=auth_headers,
    )
    assert res.status_code == 200
    rows = res.json()
    assert any(r["product_id"] == pid for r in rows)
    assert all(r["product_id"] == pid for r in rows)


def test_reconciliation_includes_adjustments(
    client, auth_headers, test_category_id, test_supplier_id
):
    """Reconciliation expected/difference should reflect recorded adjustments."""
    from datetime import date

    marker = f"__test_recon_adj_{int(time.time())}__"
    pid = _make_product(client, auth_headers, test_category_id, test_supplier_id, marker, stock=20)

    # Adjust down to 18 (diff = -2)
    client.post(
        "/api/v1/stock-adjustments",
        json={"product_id": pid, "counted_quantity": 18, "reason": marker},
        headers=auth_headers,
    )

    today = date.today().isoformat()
    rec = client.get(
        "/api/v1/reports/reconciliation",
        params={"date_from": today, "date_to": today},
        headers=auth_headers,
    ).json()
    row = next((r for r in rec if r["product_id"] == pid), None)
    assert row is not None
    assert row["total_adjustments"] == -2
    assert row["actual_stock"] == 18
    assert row["expected_stock"] == 20  # what stock would be without the adjustment
    assert row["difference"] == -2
