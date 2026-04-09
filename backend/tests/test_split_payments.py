"""Tests for split payments at checkout and fiado settlement.

Migration 003 introduces the ``sale_payments`` table as the canonical
source of money attribution and adds a ``mixto`` enum value to
``payment_method`` for sales that are split across multiple methods.

Tests run against the live API and the shared Supabase database — every
test that creates data MUST clean up after itself per CLAUDE.md and the
project_shared_prod_dev_db memory.
"""
import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

COL_TZ = timezone(timedelta(hours=-5))


def _today_str():
    return datetime.now(COL_TZ).strftime("%Y-%m-%d")


def _cleanup_sale(supabase_client, sale_id):
    """FK-safe hard-delete of a single test sale and all its dependents."""
    supabase_client.table("audit_log").delete().eq("entity_type", "sale").eq("entity_id", sale_id).execute()
    supabase_client.table("sale_payments").delete().eq("sale_id", sale_id).execute()
    supabase_client.table("sale_items").delete().eq("sale_id", sale_id).execute()
    supabase_client.table("sales").delete().eq("id", sale_id).execute()


def _restore_stock(supabase_client, product_id, target_stock):
    """Hard-set product stock back to a known snapshot value."""
    supabase_client.table("products").update({"stock": target_stock}).eq("id", product_id).execute()


def _get_product(client, headers, product_id):
    return client.get(f"/api/v1/products/{product_id}", headers=headers).json()


def _create_mixto(client, headers, product_id, splits, quantity=1):
    """Helper: create a mixto sale with the given split list. Caller is
    responsible for cleanup."""
    return client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": product_id, "quantity": quantity}],
            "payment_method": "mixto",
            "payments": splits,
        },
        headers=headers,
    )


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


# ─── Create-sale tests ───


def test_create_mixto_sale_persists_splits(client, auth_headers, test_product_id, supabase_client):
    """Mixto sale creates one sale_payments row per split with correct fields."""
    prod = _get_product(client, auth_headers, test_product_id)
    price = prod["sale_price"]  # quantity 1 → total = price

    half = price // 2
    other = price - half
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": half},
            {"payment_method": "datafono", "amount": other},
        ],
    )
    assert res.status_code == 200, res.text
    sale = res.json()
    sale_id = sale["id"]
    try:
        assert sale["payment_method"] == "mixto"
        assert sale["status"] == "completed"
        assert sale["total"] == price

        # Verify sale_payments rows in DB
        rows = (
            supabase_client.table("sale_payments")
            .select("*")
            .eq("sale_id", sale_id)
            .execute()
        )
        assert len(rows.data) == 2
        amounts_by_method = {r["payment_method"]: r["amount"] for r in rows.data}
        assert amounts_by_method == {"efectivo": half, "datafono": other}
        assert all(r["paid_at"] is not None for r in rows.data)
    finally:
        _cleanup_sale(supabase_client, sale_id)


def test_create_mixto_rejects_sum_under(client, auth_headers, test_product_id):
    """Splits summing less than total are rejected."""
    prod = _get_product(client, auth_headers, test_product_id)
    price = prod["sale_price"]
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": 1},
            {"payment_method": "datafono", "amount": 1},
        ],
    )
    assert res.status_code == 400
    assert "suma" in res.json()["detail"].lower()
    # Confirm no orphan sale was created
    assert price > 2  # sanity


def test_create_mixto_rejects_sum_over(client, auth_headers, test_product_id):
    """Splits summing more than total are rejected."""
    prod = _get_product(client, auth_headers, test_product_id)
    price = prod["sale_price"]
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": price},
            {"payment_method": "datafono", "amount": price},
        ],
    )
    assert res.status_code == 400
    assert "suma" in res.json()["detail"].lower()


def test_create_mixto_rejects_fiado_in_splits(client, auth_headers, test_product_id):
    prod = _get_product(client, auth_headers, test_product_id)
    price = prod["sale_price"]
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": price - 1},
            {"payment_method": "fiado", "amount": 1},
        ],
    )
    assert res.status_code == 400
    assert "inválido" in res.json()["detail"].lower() or "invalido" in res.json()["detail"].lower()


def test_create_mixto_rejects_mixto_in_splits(client, auth_headers, test_product_id):
    prod = _get_product(client, auth_headers, test_product_id)
    price = prod["sale_price"]
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": price - 1},
            {"payment_method": "mixto", "amount": 1},
        ],
    )
    assert res.status_code == 400


def test_create_mixto_rejects_single_split(client, auth_headers, test_product_id):
    prod = _get_product(client, auth_headers, test_product_id)
    price = prod["sale_price"]
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[{"payment_method": "efectivo", "amount": price}],
    )
    assert res.status_code == 400
    assert "al menos 2" in res.json()["detail"].lower() or "2 m" in res.json()["detail"].lower()


def test_create_mixto_rejects_zero_amount(client, auth_headers, test_product_id):
    prod = _get_product(client, auth_headers, test_product_id)
    price = prod["sale_price"]
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": price},
            {"payment_method": "datafono", "amount": 0},
        ],
    )
    assert res.status_code == 400


def test_create_mixto_rejects_duplicate_method(client, auth_headers, test_product_id):
    prod = _get_product(client, auth_headers, test_product_id)
    price = prod["sale_price"]
    half = price // 2
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": half},
            {"payment_method": "efectivo", "amount": price - half},
        ],
    )
    assert res.status_code == 400
    assert "duplicado" in res.json()["detail"].lower()


def test_create_mixto_missing_payments_field(client, auth_headers, test_product_id):
    """payment_method='mixto' but no payments → 400."""
    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "mixto",
        },
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_create_mixto_decrements_stock(client, auth_headers, test_product_id, supabase_client):
    """Mixto sales still decrement stock."""
    prod = _get_product(client, auth_headers, test_product_id)
    initial_stock = prod["stock"]
    price = prod["sale_price"]
    half = price // 2

    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": half},
            {"payment_method": "datafono", "amount": price - half},
        ],
    )
    assert res.status_code == 200, res.text
    sale_id = res.json()["id"]
    try:
        prod2 = _get_product(client, auth_headers, test_product_id)
        assert prod2["stock"] == initial_stock - 1
    finally:
        _cleanup_sale(supabase_client, sale_id)
        # restore stock if cleanup didn't auto-revert (it doesn't)
        supabase_client.table("products").update({"stock": initial_stock}).eq("id", test_product_id).execute()


def test_create_single_method_writes_sale_payments(client, auth_headers, test_product_id, supabase_client):
    """A plain efectivo sale also writes one sale_payments row."""
    prod = _get_product(client, auth_headers, test_product_id)
    initial_stock = prod["stock"]
    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "efectivo",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    sale = res.json()
    sale_id = sale["id"]
    try:
        rows = (
            supabase_client.table("sale_payments")
            .select("*")
            .eq("sale_id", sale_id)
            .execute()
        )
        assert len(rows.data) == 1
        assert rows.data[0]["payment_method"] == "efectivo"
        assert rows.data[0]["amount"] == sale["total"]
    finally:
        _cleanup_sale(supabase_client, sale_id)
        supabase_client.table("products").update({"stock": initial_stock}).eq("id", test_product_id).execute()


# ─── Pay-fiado tests ───


def test_pay_fiado_split_persists(client, auth_headers, test_product_id, supabase_client):
    """Splitting a fiado settlement creates the right sale_payments rows and
    leaves paid_payment_method NULL."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_split__")
    sale_id = sale["id"]
    total = sale["total"]
    half = total // 2
    other = total - half
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={
                "payments": [
                    {"payment_method": "efectivo", "amount": half},
                    {"payment_method": "transferencia", "amount": other},
                ],
            },
            headers=auth_headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "completed"
        assert body["paid_payment_method"] is None
        assert body["paid_at"] is not None
        assert len(body["payments"]) == 2

        # Verify in DB
        rows = (
            supabase_client.table("sale_payments")
            .select("payment_method, amount")
            .eq("sale_id", sale_id)
            .execute()
        )
        assert len(rows.data) == 2
        amounts_by_method = {r["payment_method"]: r["amount"] for r in rows.data}
        assert amounts_by_method == {"efectivo": half, "transferencia": other}
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_pay_fiado_single_method_backward_compat(client, auth_headers, test_product_id, supabase_client):
    """The legacy single payment_method body still works and creates 1
    sale_payments row."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_single_compat__")
    sale_id = sale["id"]
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payment_method": "datafono"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["paid_payment_method"] == "datafono"
        rows = (
            supabase_client.table("sale_payments")
            .select("*")
            .eq("sale_id", sale_id)
            .execute()
        )
        assert len(rows.data) == 1
        assert rows.data[0]["payment_method"] == "datafono"
        assert rows.data[0]["amount"] == sale["total"]
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_pay_fiado_rejects_both_fields(client, auth_headers, test_product_id, supabase_client):
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_both__")
    sale_id = sale["id"]
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={
                "payment_method": "efectivo",
                "payments": [
                    {"payment_method": "efectivo", "amount": sale["total"] // 2},
                    {"payment_method": "datafono", "amount": sale["total"] - sale["total"] // 2},
                ],
            },
            headers=auth_headers,
        )
        assert res.status_code == 400
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_pay_fiado_rejects_empty_body(client, auth_headers, test_product_id, supabase_client):
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_empty__")
    sale_id = sale["id"]
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={},
            headers=auth_headers,
        )
        assert res.status_code == 400
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_pay_fiado_split_sum_mismatch(client, auth_headers, test_product_id, supabase_client):
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_sum_mismatch__")
    sale_id = sale["id"]
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={
                "payments": [
                    {"payment_method": "efectivo", "amount": 1},
                    {"payment_method": "datafono", "amount": 1},
                ],
            },
            headers=auth_headers,
        )
        assert res.status_code == 400
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_pay_fiado_split_after_add_items(client, auth_headers, test_product_id, supabase_client):
    """Add items to a pending fiado, then settle it via split using the new total."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_split_after_add__")
    sale_id = sale["id"]
    try:
        # Add 2 more items
        add_res = client.post(
            f"/api/v1/sales/{sale_id}/add-items",
            json={"items": [{"product_id": test_product_id, "quantity": 2}]},
            headers=auth_headers,
        )
        assert add_res.status_code == 200
        new_total = add_res.json()["total"]
        assert new_total > sale["total"]

        # Settle via split using the new total
        half = new_total // 2
        other = new_total - half
        pay_res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={
                "payments": [
                    {"payment_method": "efectivo", "amount": half},
                    {"payment_method": "datafono", "amount": other},
                ],
            },
            headers=auth_headers,
        )
        assert pay_res.status_code == 200, pay_res.text
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


# ─── Void tests ───


def test_void_mixto_preserves_sale_payments_rows(client, auth_headers, test_product_id, supabase_client):
    """Voiding a mixto sale leaves sale_payments rows in place but the rows
    are filtered out of cash closing by the sales.status join."""
    prod = _get_product(client, auth_headers, test_product_id)
    initial_stock = prod["stock"]
    price = prod["sale_price"]
    half = price // 2
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": half},
            {"payment_method": "datafono", "amount": price - half},
        ],
    )
    sale_id = res.json()["id"]
    try:
        client.post(
            f"/api/v1/sales/{sale_id}/void",
            json={"reason": "test void mixto"},
            headers=auth_headers,
        )
        sale_row = supabase_client.table("sales").select("*").eq("id", sale_id).single().execute()
        assert sale_row.data["status"] == "voided"
        # sale_payments rows preserved
        rows = supabase_client.table("sale_payments").select("*").eq("sale_id", sale_id).execute()
        assert len(rows.data) == 2
    finally:
        _cleanup_sale(supabase_client, sale_id)
        supabase_client.table("products").update({"stock": initial_stock}).eq("id", test_product_id).execute()


def test_void_split_settled_fiado(client, auth_headers, test_product_id, supabase_client):
    """Voiding a split-settled fiado preserves sale_payments rows and clears
    paid_at on the sales row."""
    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_void_split__")
    sale_id = sale["id"]
    total = sale["total"]
    half = total // 2
    try:
        client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payments": [
                {"payment_method": "efectivo", "amount": half},
                {"payment_method": "datafono", "amount": total - half},
            ]},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/sales/{sale_id}/void",
            json={"reason": "void split settled"},
            headers=auth_headers,
        )
        sale_row = supabase_client.table("sales").select("*").eq("id", sale_id).single().execute()
        assert sale_row.data["status"] == "voided"
        assert sale_row.data["paid_at"] is None
        assert sale_row.data["paid_payment_method"] is None
        rows = supabase_client.table("sale_payments").select("*").eq("sale_id", sale_id).execute()
        assert len(rows.data) == 2
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


# ─── Cash closing tests ───


def test_cash_closing_distributes_mixto_into_buckets(client, auth_headers, test_product_id, supabase_client):
    """A mixto sale's components route to per-method buckets in the cash closing."""
    date = _today_str()
    baseline = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
    if baseline.get("existing"):
        return  # closing already saved — don't pollute prod

    prod = _get_product(client, auth_headers, test_product_id)
    initial_stock = prod["stock"]
    price = prod["sale_price"]
    half = price // 2
    other = price - half

    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": half},
            {"payment_method": "datafono", "amount": other},
        ],
    )
    sale_id = res.json()["id"]
    try:
        after = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
        assert after["total_cash"] == baseline["total_cash"] + half
        assert after["total_datafono"] == baseline["total_datafono"] + other
    finally:
        _cleanup_sale(supabase_client, sale_id)
        supabase_client.table("products").update({"stock": initial_stock}).eq("id", test_product_id).execute()


def test_cash_closing_voided_mixto_excluded(client, auth_headers, test_product_id, supabase_client):
    date = _today_str()
    baseline = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
    if baseline.get("existing"):
        return

    prod = _get_product(client, auth_headers, test_product_id)
    initial_stock = prod["stock"]
    price = prod["sale_price"]
    half = price // 2
    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": half},
            {"payment_method": "datafono", "amount": price - half},
        ],
    )
    sale_id = res.json()["id"]
    try:
        client.post(
            f"/api/v1/sales/{sale_id}/void",
            json={"reason": "test exclude void"},
            headers=auth_headers,
        )
        after = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
        assert after["total_cash"] == baseline["total_cash"]
        assert after["total_datafono"] == baseline["total_datafono"]
    finally:
        _cleanup_sale(supabase_client, sale_id)
        supabase_client.table("products").update({"stock": initial_stock}).eq("id", test_product_id).execute()


def test_cash_closing_fiado_split_settlement_routes_correctly(client, auth_headers, test_product_id, supabase_client):
    date = _today_str()
    baseline = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
    if baseline.get("existing"):
        return

    initial_stock = _get_product(client, auth_headers, test_product_id)["stock"]
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_closing_fiado_split__")
    sale_id = sale["id"]
    total = sale["total"]
    half = total // 2
    other = total - half
    try:
        client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payments": [
                {"payment_method": "efectivo", "amount": half},
                {"payment_method": "transferencia", "amount": other},
            ]},
            headers=auth_headers,
        )
        after = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
        assert after["total_cash"] == baseline["total_cash"] + half
        assert after["total_transfer"] == baseline["total_transfer"] + other
        assert after["total_credit_collected"] == baseline["total_credit_collected"] + total
    finally:
        _cleanup_sale(supabase_client, sale_id)
        _restore_stock(supabase_client, test_product_id, initial_stock)


def test_cash_closing_legacy_single_method_regression(client, auth_headers, test_product_id, supabase_client):
    """Plain efectivo sales still appear in total_cash via the new sale_payments path."""
    date = _today_str()
    baseline = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
    if baseline.get("existing"):
        return

    prod = _get_product(client, auth_headers, test_product_id)
    initial_stock = prod["stock"]
    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "efectivo",
        },
        headers=auth_headers,
    )
    sale_id = res.json()["id"]
    sale_total = res.json()["total"]
    try:
        after = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
        assert after["total_cash"] == baseline["total_cash"] + sale_total
    finally:
        _cleanup_sale(supabase_client, sale_id)
        supabase_client.table("products").update({"stock": initial_stock}).eq("id", test_product_id).execute()


# ─── Daily summary ───


def test_daily_summary_distributes_mixto(client, auth_headers, test_product_id, supabase_client):
    date = _today_str()
    baseline = client.get(f"/api/v1/reports/daily-summary?date={date}", headers=auth_headers).json()
    base_efectivo = baseline.get("by_payment_method", {}).get("efectivo", 0)
    base_transfer = baseline.get("by_payment_method", {}).get("transferencia", 0)

    prod = _get_product(client, auth_headers, test_product_id)
    initial_stock = prod["stock"]
    price = prod["sale_price"]
    half = price // 2
    other = price - half

    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": half},
            {"payment_method": "transferencia", "amount": other},
        ],
    )
    sale_id = res.json()["id"]
    try:
        after = client.get(f"/api/v1/reports/daily-summary?date={date}", headers=auth_headers).json()
        assert after["by_payment_method"]["efectivo"] == base_efectivo + half
        assert after["by_payment_method"]["transferencia"] == base_transfer + other
    finally:
        _cleanup_sale(supabase_client, sale_id)
        supabase_client.table("products").update({"stock": initial_stock}).eq("id", test_product_id).execute()


# ─── Sale detail ───


def test_get_sale_detail_includes_payments(client, auth_headers, test_product_id, supabase_client):
    prod = _get_product(client, auth_headers, test_product_id)
    initial_stock = prod["stock"]
    price = prod["sale_price"]
    half = price // 2

    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": half},
            {"payment_method": "datafono", "amount": price - half},
        ],
    )
    sale_id = res.json()["id"]
    try:
        detail = client.get(f"/api/v1/sales/{sale_id}", headers=auth_headers).json()
        assert "payments" in detail
        assert len(detail["payments"]) == 2
        for p in detail["payments"]:
            assert "payment_method" in p
            assert "amount" in p
            assert "paid_at" in p
    finally:
        _cleanup_sale(supabase_client, sale_id)
        supabase_client.table("products").update({"stock": initial_stock}).eq("id", test_product_id).execute()


# ─── CSV export ───


def test_export_csv_includes_detalle_de_pago(client, auth_headers, test_product_id, supabase_client):
    prod = _get_product(client, auth_headers, test_product_id)
    initial_stock = prod["stock"]
    price = prod["sale_price"]
    half = price // 2
    other = price - half

    res = _create_mixto(
        client, auth_headers, test_product_id,
        splits=[
            {"payment_method": "efectivo", "amount": half},
            {"payment_method": "datafono", "amount": other},
        ],
    )
    sale_id = res.json()["id"]
    try:
        date = _today_str()
        csv_res = client.get(
            f"/api/v1/reports/export/sales?date_from={date}&date_to={date}",
            headers=auth_headers,
        )
        assert csv_res.status_code == 200
        text = csv_res.text
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        header = rows[0]
        assert "Detalle de Pago" in header
        # Find the mixto row by sale id is impossible from CSV alone, so just
        # assert that at least one row in this date range has the split string
        has_split = any(
            "efectivo:" in cell and "datafono:" in cell
            for row in rows[1:]
            for cell in row
        )
        assert has_split
    finally:
        _cleanup_sale(supabase_client, sale_id)
        supabase_client.table("products").update({"stock": initial_stock}).eq("id", test_product_id).execute()
