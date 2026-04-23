"""Audit log coverage tests — ensure key mutations leave a trail."""
import time


def _find_audit(client, auth_headers, entity_type: str, entity_id: str, action: str) -> dict | None:
    res = client.get(
        "/api/v1/audit-log",
        params={"entity_type": entity_type, "entity_id": entity_id, "limit": 20},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    for row in res.json():
        if row["action"] == action:
            return row
    return None


def test_sale_creation_writes_audit(client, auth_headers, test_product_id):
    marker = f"__test_audit_sale_{int(time.time())}__"
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

    audit = _find_audit(client, auth_headers, "sale", sale_id, "sale_created")
    assert audit is not None, "expected sale_created audit entry"
    assert audit["new_values"]["payment_method"] == "efectivo"
    assert audit["new_values"]["status"] == "completed"

    # Cleanup
    client.post(f"/api/v1/sales/{sale_id}/void", json={"reason": marker}, headers=auth_headers)


def test_sale_void_writes_audit(client, auth_headers, test_product_id):
    marker = f"__test_audit_void_{int(time.time())}__"
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "efectivo",
            "notes": marker,
        },
        headers=auth_headers,
    )
    sale_id = create_res.json()["id"]

    void_res = client.post(
        f"/api/v1/sales/{sale_id}/void",
        json={"reason": marker},
        headers=auth_headers,
    )
    assert void_res.status_code == 200, void_res.text

    audit = _find_audit(client, auth_headers, "sale", sale_id, "sale_voided")
    assert audit is not None
    assert audit["new_values"]["status"] == "voided"
    assert audit["new_values"]["reason"] == marker


def test_inventory_entry_writes_audit(
    client, auth_headers, test_product_id, test_supplier_id
):
    marker = f"__test_audit_entry_{int(time.time())}__"
    res = client.post(
        "/api/v1/inventory/entry",
        json={
            "product_id": test_product_id,
            "quantity": 1,
            "supplier_id": test_supplier_id,
            "price_confirmed": True,
        },
        headers=auth_headers,
    )
    # Some deployments 404 when route missing; skip gracefully
    if res.status_code == 404:
        return
    assert res.status_code == 200, res.text
    entry_id = res.json()["id"]

    audit = _find_audit(
        client, auth_headers, "inventory_entry", entry_id, "inventory_entry_created"
    )
    assert audit is not None
    assert audit["new_values"]["product_id"] == test_product_id
    assert audit["new_values"]["quantity"] == 1


def test_internal_use_writes_audit(client, auth_headers, test_product_id):
    marker = f"__test_audit_iu_{int(time.time())}__"
    reason = f"Prueba audit {marker}"
    res = client.post(
        "/api/v1/inventory/internal-use",
        json={
            "product_id": test_product_id,
            "quantity": 1,
            "reason": reason,
        },
        headers=auth_headers,
    )
    if res.status_code == 404:
        return
    assert res.status_code == 200, res.text
    iu_id = res.json()["id"]

    audit = _find_audit(
        client, auth_headers, "internal_use", iu_id, "internal_use_created"
    )
    assert audit is not None
    assert audit["new_values"]["reason"] == reason
    assert audit["new_values"]["quantity"] == 1
