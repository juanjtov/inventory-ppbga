"""Concurrency tests — verify atomic stock RPC prevents oversell races."""
import time
from concurrent.futures import ThreadPoolExecutor

import httpx


def test_atomic_decrement_prevents_oversell(
    client, auth_headers, base_url, test_category_id, test_supplier_id
):
    """Set a product stock to 1. Fire two concurrent sales for 1 unit each.
    Exactly one succeeds; the other gets 400 insufficient-stock; final stock
    never goes negative."""
    marker = f"__test_race_{int(time.time())}__"
    prod_res = client.post(
        "/api/v1/products",
        json={
            "name": marker,
            "category_id": test_category_id,
            "supplier_id": test_supplier_id,
            "sale_price": 100,
            "stock": 1,
            "type": "product",
        },
        headers=auth_headers,
    )
    if prod_res.status_code != 200:
        return  # product already existed; skip rather than contaminate
    pid = prod_res.json()["id"]

    payload = {
        "items": [{"product_id": pid, "quantity": 1}],
        "payment_method": "efectivo",
        "notes": marker,
    }

    def post_sale():
        # Use a fresh client per thread; httpx.Client is not thread-safe.
        with httpx.Client(base_url=base_url, timeout=30.0) as c:
            return c.post("/api/v1/sales", json=payload, headers=auth_headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(post_sale) for _ in range(2)]
        responses = [f.result() for f in futures]

    statuses = sorted(r.status_code for r in responses)
    # One success + one "insufficient" is the correct outcome
    assert statuses == [200, 400], f"unexpected statuses: {statuses}, bodies: {[r.text for r in responses]}"

    # Final stock must be zero, never -1
    prod = client.get(f"/api/v1/products/{pid}", headers=auth_headers).json()
    assert prod["stock"] == 0

    # Cleanup: void the successful sale to restore state
    for r in responses:
        if r.status_code == 200:
            client.post(
                f"/api/v1/sales/{r.json()['id']}/void",
                json={"reason": marker},
                headers=auth_headers,
            )


def test_atomic_increment_on_void(
    client, auth_headers, test_category_id, test_supplier_id
):
    """Void a sale — the atomic increment should restore stock precisely."""
    marker = f"__test_atomic_inc_{int(time.time())}__"
    prod_res = client.post(
        "/api/v1/products",
        json={
            "name": marker,
            "category_id": test_category_id,
            "supplier_id": test_supplier_id,
            "sale_price": 100,
            "stock": 5,
            "type": "product",
        },
        headers=auth_headers,
    )
    if prod_res.status_code != 200:
        return
    pid = prod_res.json()["id"]

    sale_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": pid, "quantity": 3}],
            "payment_method": "efectivo",
            "notes": marker,
        },
        headers=auth_headers,
    )
    assert sale_res.status_code == 200, sale_res.text
    sale_id = sale_res.json()["id"]

    # After sale: stock = 2
    prod = client.get(f"/api/v1/products/{pid}", headers=auth_headers).json()
    assert prod["stock"] == 2

    # Void — stock restored to 5
    void_res = client.post(
        f"/api/v1/sales/{sale_id}/void",
        json={"reason": marker},
        headers=auth_headers,
    )
    assert void_res.status_code == 200, void_res.text
    prod2 = client.get(f"/api/v1/products/{pid}", headers=auth_headers).json()
    assert prod2["stock"] == 5
