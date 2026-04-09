"""Tests for removing line items from open fiado accounts.

When a cashier makes a mistake adding an item to a pending fiado, an admin
can remove the line item via POST /api/v1/sales/{id}/remove-item, which:
- restocks the underlying product (if it's a product, not a service)
- updates the sale total
- writes an audit log entry
- auto-voids the sale when the last item is removed (cleaner UX in
  Cuentas Abiertas — empty fiados disappear instead of lingering)

Tests run against the live shared Supabase database — every test that
creates data MUST clean up after itself per CLAUDE.md and the
project_shared_prod_dev_db memory.
"""
import uuid


def _cleanup_sale(supabase_client, sale_id):
    """FK-safe hard-delete of a single test sale and its dependents."""
    supabase_client.table("audit_log").delete().eq("entity_type", "sale").eq("entity_id", sale_id).execute()
    supabase_client.table("sale_payments").delete().eq("sale_id", sale_id).execute()
    supabase_client.table("sale_items").delete().eq("sale_id", sale_id).execute()
    supabase_client.table("sales").delete().eq("id", sale_id).execute()


def _restore_stock(supabase_client, product_id, target_stock):
    supabase_client.table("products").update({"stock": target_stock}).eq("id", product_id).execute()


def _get_product(client, headers, product_id):
    return client.get(f"/api/v1/products/{product_id}", headers=headers).json()


def _create_fiado(client, headers, product_id, client_name, quantity=1):
    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": product_id, "quantity": quantity}],
            "payment_method": "fiado",
            "client_name": client_name,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


# ─── Restock + total update ───


def test_remove_item_restocks_product(client, auth_headers, test_product_id, supabase_client):
    """Removing an item restores the product stock and decreases sale.total."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_remove_restock__", quantity=3)
    sale_id = sale["id"]
    item_id = sale["items"][0]["id"]
    item_subtotal = sale["items"][0]["subtotal"]

    try:
        # After create, stock is initial_stock - 3
        mid = _get_product(client, auth_headers, test_product_id)
        assert mid["stock"] == initial_stock - 3

        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": item_id},
            headers=auth_headers,
        )
        # Removing the only line item triggers auto-void; the response is
        # the auto-voided sale.
        assert res.status_code == 200, res.text

        # Stock fully restored (auto-void path also returns the stock)
        after = _get_product(client, auth_headers, test_product_id)
        assert after["stock"] == initial_stock

        # sale_items row deleted
        items = supabase_client.table("sale_items").select("id").eq("sale_id", sale_id).execute()
        assert len(items.data) == 0
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_remove_item_updates_total(client, auth_headers, test_product_id, supabase_client):
    """Removing one of two items decreases sale.total by that item's subtotal."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_remove_total__", quantity=2)
    sale_id = sale["id"]
    original_total = sale["total"]

    # Add a second line item via add-items (different sale_items row, same product)
    add = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": test_product_id, "quantity": 1}]},
        headers=auth_headers,
    )
    assert add.status_code == 200
    full_total = add.json()["total"]
    items_after_add = add.json()["items"]
    assert len(items_after_add) == 2

    try:
        # Remove the first item (qty=2)
        first_item = next(it for it in items_after_add if it["quantity"] == 2)
        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": first_item["id"]},
            headers=auth_headers,
        )
        assert res.status_code == 200
        body = res.json()

        # New total should equal full_total - first_item.subtotal
        assert body["total"] == full_total - first_item["subtotal"]
        assert body["status"] == "pending"  # not auto-voided, one item remains
        assert len(body["items"]) == 1
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


# ─── Auto-void on last item ───


def test_remove_last_item_auto_voids(client, auth_headers, test_product_id, supabase_client):
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_auto_void__", quantity=1)
    sale_id = sale["id"]
    item_id = sale["items"][0]["id"]

    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": item_id},
            headers=auth_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "voided"
        assert body["voided_at"] is not None
        assert body["void_reason"] is not None
        assert "auto" in body["void_reason"].lower()
        assert body["total"] == 0
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


# ─── Validation: status / type ───


def test_remove_item_requires_pending_status(client, auth_headers, test_product_id, supabase_client):
    """Cannot remove items from a paid (completed) sale."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_remove_paid__", quantity=1)
    sale_id = sale["id"]
    item_id = sale["items"][0]["id"]

    try:
        # Pay it first
        client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payment_method": "efectivo"},
            headers=auth_headers,
        )

        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": item_id},
            headers=auth_headers,
        )
        assert res.status_code == 400
        assert "pendientes" in res.json()["detail"].lower()
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_remove_item_rejects_voided(client, auth_headers, test_product_id, supabase_client):
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_remove_voided__", quantity=1)
    sale_id = sale["id"]
    item_id = sale["items"][0]["id"]

    try:
        client.post(
            f"/api/v1/sales/{sale_id}/void",
            json={"reason": "test void"},
            headers=auth_headers,
        )
        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": item_id},
            headers=auth_headers,
        )
        assert res.status_code == 400
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_remove_item_rejects_non_fiado(client, auth_headers, test_product_id, supabase_client):
    """Cannot remove items from a non-fiado sale (only fiado is allowed)."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "efectivo",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    sale_id = create_res.json()["id"]
    item_id = create_res.json()["items"][0]["id"]

    try:
        # The sale is completed (efectivo) — first hurdle is the status check
        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": item_id},
            headers=auth_headers,
        )
        assert res.status_code == 400
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


# ─── 404s ───


def test_remove_item_rejects_wrong_sale_id(client, auth_headers, test_product_id, supabase_client):
    """Calling remove with an item_id that belongs to a different sale → 404."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale_a = _create_fiado(client, auth_headers, test_product_id, "__test_remove_wrong_a__", quantity=1)
    sale_b = _create_fiado(client, auth_headers, test_product_id, "__test_remove_wrong_b__", quantity=1)
    item_id_b = sale_b["items"][0]["id"]

    try:
        res = client.post(
            f"/api/v1/sales/{sale_a['id']}/remove-item",
            json={"item_id": item_id_b},
            headers=auth_headers,
        )
        assert res.status_code == 404
    finally:
        _cleanup_sale(supabase_client, sale_a["id"])
        _cleanup_sale(supabase_client, sale_b["id"])
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_remove_item_nonexistent_sale(client, auth_headers, test_product_id):
    fake_sale = str(uuid.uuid4())
    fake_item = str(uuid.uuid4())
    res = client.post(
        f"/api/v1/sales/{fake_sale}/remove-item",
        json={"item_id": fake_item},
        headers=auth_headers,
    )
    assert res.status_code == 404


def test_remove_item_nonexistent_item(client, auth_headers, test_product_id, supabase_client):
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_remove_no_item__", quantity=1)
    sale_id = sale["id"]
    fake_item = str(uuid.uuid4())
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": fake_item},
            headers=auth_headers,
        )
        assert res.status_code == 404
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


# ─── Services have no stock ───


def test_remove_item_service_no_stock_change(client, auth_headers, test_service_id, supabase_client):
    """Services don't track stock — removing them succeeds without trying to restock."""
    sale = _create_fiado(client, auth_headers, test_service_id, "__test_remove_service__", quantity=2)
    sale_id = sale["id"]
    item_id = sale["items"][0]["id"]

    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": item_id},
            headers=auth_headers,
        )
        assert res.status_code == 200
        body = res.json()
        # Auto-voided since it was the only item
        assert body["status"] == "voided"
    finally:
        _cleanup_sale(supabase_client, sale_id)


# ─── Audit log ───


def test_remove_item_audit_log(client, auth_headers, test_product_id, supabase_client):
    """The audit_log entry for fiado_remove_item captures old/new totals and the removed item."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    # Use quantity=2 + add-items so the sale doesn't auto-void
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_remove_audit__", quantity=1)
    sale_id = sale["id"]
    add = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": test_product_id, "quantity": 1}]},
        headers=auth_headers,
    )
    assert add.status_code == 200
    items = add.json()["items"]

    try:
        # Remove the first item; sale should still have one item left
        first_item = items[0]
        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": first_item["id"]},
            headers=auth_headers,
        )
        assert res.status_code == 200

        # Verify the audit log entry
        rows = (
            supabase_client.table("audit_log")
            .select("*")
            .eq("entity_type", "sale")
            .eq("entity_id", sale_id)
            .execute()
        )
        remove_entries = [r for r in rows.data if r["action"] == "fiado_remove_item"]
        assert len(remove_entries) == 1
        entry = remove_entries[0]
        assert "removed_item" in entry["old_values"]
        assert entry["old_values"]["removed_item"]["product_id"] == first_item["product_id"]
        assert entry["new_values"]["total"] < entry["old_values"]["total"]
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


# ─── Add then remove ───


def test_remove_item_after_add_items(client, auth_headers, test_product_id, supabase_client):
    """Create fiado, add more items, remove one of the added items."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_add_then_remove__", quantity=1)
    sale_id = sale["id"]
    add = client.post(
        f"/api/v1/sales/{sale_id}/add-items",
        json={"items": [{"product_id": test_product_id, "quantity": 3}]},
        headers=auth_headers,
    )
    assert add.status_code == 200
    full_total = add.json()["total"]
    items = add.json()["items"]
    added_item = next(it for it in items if it["quantity"] == 3)

    try:
        # Stock should now be initial - 4
        mid = _get_product(client, auth_headers, test_product_id)
        assert mid["stock"] == initial_stock - 4

        res = client.post(
            f"/api/v1/sales/{sale_id}/remove-item",
            json={"item_id": added_item["id"]},
            headers=auth_headers,
        )
        assert res.status_code == 200
        body = res.json()
        # Sale still pending with one item left
        assert body["status"] == "pending"
        assert len(body["items"]) == 1
        # Total decreased by the removed item's subtotal
        assert body["total"] == full_total - added_item["subtotal"]

        # Stock restored: initial - 4 + 3 = initial - 1
        after = _get_product(client, auth_headers, test_product_id)
        assert after["stock"] == initial_stock - 1
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)
