"""Tests for payment-method capture on fiado settlement and money-flow cash closing.

These tests exercise migration 002 (paid_payment_method, paid_at columns and the
extended cash_closings totals). They run against the live API and the shared
Supabase database — every test that creates data MUST clean up after itself.

Per CLAUDE.md and project_shared_prod_dev_db memory: hard-delete all test
artifacts in FK-safe order (audit_log → sale_items → sales).
"""
import uuid
from datetime import datetime, timedelta, timezone

COL_TZ = timezone(timedelta(hours=-5))


def _today_str():
    return datetime.now(COL_TZ).strftime("%Y-%m-%d")


def _cleanup_sale(supabase_client, sale_id):
    """FK-safe hard-delete of a single test sale and its dependents."""
    supabase_client.table("audit_log").delete().eq("entity_type", "sale").eq("entity_id", sale_id).execute()
    supabase_client.table("sale_payments").delete().eq("sale_id", sale_id).execute()
    supabase_client.table("sale_items").delete().eq("sale_id", sale_id).execute()
    supabase_client.table("sales").delete().eq("id", sale_id).execute()


def _create_fiado(client, headers, product_id, client_name):
    res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": client_name,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


# ── /pay endpoint validation ──


def test_pay_persists_method_and_timestamp(client, auth_headers, test_product_id, supabase_client):
    """Marking a fiado as paid persists paid_payment_method and paid_at."""
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_persist__")
    sale_id = sale["id"]
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payment_method": "datafono"},
            headers=auth_headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "completed"
        assert body["paid_payment_method"] == "datafono"
        assert body["paid_at"] is not None

        # Verify directly in DB
        row = supabase_client.table("sales").select("*").eq("id", sale_id).single().execute()
        assert row.data["paid_payment_method"] == "datafono"
        assert row.data["paid_at"] is not None
    finally:
        _cleanup_sale(supabase_client, sale_id)


def test_pay_audit_log_records_method(client, auth_headers, test_product_id, supabase_client):
    """The audit log entry for fiado_paid includes the payment method."""
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_audit__")
    sale_id = sale["id"]
    try:
        client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payment_method": "transferencia"},
            headers=auth_headers,
        )
        rows = supabase_client.table("audit_log").select("*").eq("entity_type", "sale").eq("entity_id", sale_id).execute()
        paid_entries = [r for r in rows.data if r["action"] == "fiado_paid"]
        assert len(paid_entries) >= 1
        new_vals = paid_entries[-1]["new_values"]
        assert new_vals["status"] == "completed"
        assert new_vals["paid_payment_method"] == "transferencia"
        assert new_vals["paid_at"] is not None
    finally:
        _cleanup_sale(supabase_client, sale_id)


def test_pay_rejects_fiado_as_method(client, auth_headers, test_product_id, supabase_client):
    """Cannot settle a fiado by paying with fiado."""
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_reject_fiado__")
    sale_id = sale["id"]
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payment_method": "fiado"},
            headers=auth_headers,
        )
        assert res.status_code == 400
        assert "inválido" in res.json()["detail"].lower() or "invalido" in res.json()["detail"].lower()
    finally:
        _cleanup_sale(supabase_client, sale_id)


def test_pay_rejects_unknown_method(client, auth_headers, test_product_id, supabase_client):
    """Cannot pay with an unknown method."""
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_reject_unknown__")
    sale_id = sale["id"]
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payment_method": "bitcoin"},
            headers=auth_headers,
        )
        assert res.status_code == 400
    finally:
        _cleanup_sale(supabase_client, sale_id)


def test_pay_requires_payment_method_field(client, auth_headers, test_product_id, supabase_client):
    """The /pay endpoint requires either payment_method or payments in the body."""
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_pay_missing_field__")
    sale_id = sale["id"]
    try:
        res = client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={},
            headers=auth_headers,
        )
        # Service layer rejects empty body with 400 (split-payments era)
        assert res.status_code == 400
    finally:
        _cleanup_sale(supabase_client, sale_id)


# ── Voiding a paid fiado clears settlement state ──


def test_void_paid_fiado_clears_paid_fields(client, auth_headers, test_product_id, supabase_client):
    """Voiding a previously-paid fiado nulls paid_payment_method and paid_at."""
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_void_clears_paid__")
    sale_id = sale["id"]
    try:
        client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payment_method": "efectivo"},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/sales/{sale_id}/void",
            json={"reason": "test void clears"},
            headers=auth_headers,
        )
        row = supabase_client.table("sales").select("*").eq("id", sale_id).single().execute()
        assert row.data["status"] == "voided"
        assert row.data["paid_payment_method"] is None
        assert row.data["paid_at"] is None
    finally:
        _cleanup_sale(supabase_client, sale_id)


# ── Cash closing money-flow semantics ──


def test_cash_closing_includes_fiado_collected_in_cash(client, auth_headers, test_product_id, supabase_client):
    """A fiado paid in efectivo today should appear in total_cash on today's cash closing."""
    sale = _create_fiado(client, auth_headers, test_product_id, "__test_closing_cash_fiado__")
    sale_id = sale["id"]
    sale_total = sale["total"]
    try:
        # Get baseline
        date = _today_str()
        baseline = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
        if baseline.get("existing"):
            # Real closing already saved for today — skip rather than corrupt prod
            return
        baseline_cash = baseline["total_cash"]
        baseline_collected = baseline["total_credit_collected"]
        baseline_outstanding = baseline["total_credit_outstanding"]

        # Pay it in cash
        client.post(
            f"/api/v1/sales/{sale_id}/pay",
            json={"payment_method": "efectivo"},
            headers=auth_headers,
        )

        after = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
        assert after["total_cash"] == baseline_cash + sale_total
        assert after["total_credit_collected"] == baseline_collected + sale_total
        # Outstanding is a snapshot of all currently-pending fiado. Paying one
        # moves it from pending to completed, so the snapshot drops by sale_total.
        assert after["total_credit_outstanding"] == baseline_outstanding - sale_total
    finally:
        _cleanup_sale(supabase_client, sale_id)


def test_cash_closing_credit_issued_includes_today_fiado(client, auth_headers, test_product_id, supabase_client):
    """Creating a fiado today should bump total_credit_issued by its total."""
    date = _today_str()
    baseline = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
    if baseline.get("existing"):
        return
    baseline_issued = baseline["total_credit_issued"]
    baseline_outstanding = baseline["total_credit_outstanding"]

    sale = _create_fiado(client, auth_headers, test_product_id, "__test_closing_issued__")
    sale_id = sale["id"]
    try:
        after = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
        assert after["total_credit_issued"] == baseline_issued + sale["total"]
        assert after["total_credit_outstanding"] == baseline_outstanding + sale["total"]
    finally:
        _cleanup_sale(supabase_client, sale_id)


def test_cash_closing_paid_fiado_routes_to_correct_method(client, auth_headers, test_product_id, supabase_client):
    """Each settlement method routes to its own bucket."""
    date = _today_str()
    baseline = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
    if baseline.get("existing"):
        return

    s1 = _create_fiado(client, auth_headers, test_product_id, "__test_route_efectivo__")
    s2 = _create_fiado(client, auth_headers, test_product_id, "__test_route_datafono__")
    s3 = _create_fiado(client, auth_headers, test_product_id, "__test_route_transferencia__")
    try:
        client.post(f"/api/v1/sales/{s1['id']}/pay", json={"payment_method": "efectivo"}, headers=auth_headers)
        client.post(f"/api/v1/sales/{s2['id']}/pay", json={"payment_method": "datafono"}, headers=auth_headers)
        client.post(f"/api/v1/sales/{s3['id']}/pay", json={"payment_method": "transferencia"}, headers=auth_headers)

        after = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
        assert after["total_cash"] == baseline["total_cash"] + s1["total"]
        assert after["total_datafono"] == baseline["total_datafono"] + s2["total"]
        assert after["total_transfer"] == baseline["total_transfer"] + s3["total"]
        # All three credit_collected
        assert after["total_credit_collected"] == baseline["total_credit_collected"] + s1["total"] + s2["total"] + s3["total"]
    finally:
        _cleanup_sale(supabase_client, s1["id"])
        _cleanup_sale(supabase_client, s2["id"])
        _cleanup_sale(supabase_client, s3["id"])


def test_voided_paid_fiado_excluded_from_closing(client, auth_headers, test_product_id, supabase_client):
    """A paid fiado that gets voided should disappear from the closing totals."""
    date = _today_str()
    baseline = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
    if baseline.get("existing"):
        return

    sale = _create_fiado(client, auth_headers, test_product_id, "__test_void_excluded__")
    sale_id = sale["id"]
    try:
        client.post(f"/api/v1/sales/{sale_id}/pay", json={"payment_method": "efectivo"}, headers=auth_headers)
        # Now void
        client.post(f"/api/v1/sales/{sale_id}/void", json={"reason": "test cleanup"}, headers=auth_headers)

        after = client.get(f"/api/v1/reports/cash-closing?date={date}", headers=auth_headers).json()
        # Voided sale should not contribute to credit_collected, total_cash, or credit_issued
        assert after["total_cash"] == baseline["total_cash"]
        assert after["total_credit_collected"] == baseline["total_credit_collected"]
        assert after["total_credit_issued"] == baseline["total_credit_issued"]
    finally:
        _cleanup_sale(supabase_client, sale_id)
