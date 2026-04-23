"""Reports endpoint tests."""
from datetime import date, timedelta
import time


def test_daily_summary(client, auth_headers):
    today = date.today().isoformat()
    res = client.get(
        "/api/v1/reports/daily-summary",
        params={"date": today},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "total_sales" in data
    assert "by_payment_method" in data
    assert "top_products" in data


def test_cash_closing_data(client, auth_headers):
    today = date.today().isoformat()
    res = client.get(
        "/api/v1/reports/cash-closing",
        params={"date": today},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    # Either has existing closing or calculated data
    if data.get("existing"):
        assert "closing" in data
    else:
        assert "total_sales" in data
        assert "total_cash" in data


def test_create_cash_closing(client, auth_headers):
    """Create a cash closing for a test date."""
    test_date = "2020-01-01"  # Use old date to avoid conflicts
    res = client.post(
        "/api/v1/reports/cash-closing",
        json={
            "closing_date": test_date,
            "physical_cash": 0,
            "notes": "Test closing",
        },
        headers=auth_headers,
    )
    # Either 200 (created) or 400 (already exists)
    assert res.status_code in (200, 400)


def test_cash_closing_unique_per_day(client, auth_headers):
    """Cannot create two closings for the same date."""
    test_date = "2020-01-02"
    # First attempt
    client.post(
        "/api/v1/reports/cash-closing",
        json={"closing_date": test_date, "physical_cash": 0},
        headers=auth_headers,
    )
    # Second attempt should fail
    res = client.post(
        "/api/v1/reports/cash-closing",
        json={"closing_date": test_date, "physical_cash": 0},
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_top_sellers(client, auth_headers):
    today = date.today().isoformat()
    res = client.get(
        "/api/v1/reports/top-sellers",
        params={"period": "day", "date": today},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_top_sellers_week(client, auth_headers):
    today = date.today().isoformat()
    res = client.get(
        "/api/v1/reports/top-sellers",
        params={"period": "week", "date": today},
        headers=auth_headers,
    )
    assert res.status_code == 200


def test_top_sellers_month(client, auth_headers):
    today = date.today().isoformat()
    res = client.get(
        "/api/v1/reports/top-sellers",
        params={"period": "month", "date": today},
        headers=auth_headers,
    )
    assert res.status_code == 200


def test_inventory_value(client, auth_headers):
    res = client.get("/api/v1/reports/inventory-value", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "grand_total_sale" in data
    assert "grand_total_purchase" in data


def test_reconciliation(client, auth_headers):
    today = date.today().isoformat()
    res = client.get(
        "/api/v1/reports/reconciliation",
        params={"date_from": today, "date_to": today},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_fiado_aging(client, auth_headers):
    res = client.get("/api/v1/reports/fiado-aging", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_owed" in data
    assert "buckets" in data
    assert len(data["buckets"]) == 3


def test_export_sales(client, auth_headers):
    today = date.today().isoformat()
    res = client.get(
        "/api/v1/reports/export/sales",
        params={"date_from": today, "date_to": today},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")


# ── Phase 1 tests: money-flow semantics + historical outstanding ──


def _daily_summary(client, auth_headers, day_iso: str) -> dict:
    res = client.get(
        "/api/v1/reports/daily-summary",
        params={"date": day_iso},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


def _cash_closing(client, auth_headers, day_iso: str) -> dict:
    res = client.get(
        "/api/v1/reports/cash-closing",
        params={"date": day_iso},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_daily_summary_new_fields(client, auth_headers):
    """Money-flow response contract: new fields are present."""
    today = date.today().isoformat()
    data = _daily_summary(client, auth_headers, today)
    assert "by_payment_method" in data
    assert "fiado_pending" in data
    assert "fiado_settled_in_range" in data
    by_method = data["by_payment_method"]
    assert set(by_method.keys()) == {"efectivo", "transferencia", "datafono", "fiado"}
    # fiado bucket in money-flow view equals pending (por cobrar)
    assert by_method["fiado"] == data["fiado_pending"]


def test_daily_summary_fiado_settled_shifts_to_method(
    client, auth_headers, test_product_id
):
    """Create a fiado, settle it in cash. Money moves from fiado bucket to
    efectivo bucket. Same-day scenario: both the creation and settlement are
    captured by today's summary."""
    today = date.today().isoformat()
    marker = f"__test_shift_{int(time.time())}__"

    before = _daily_summary(client, auth_headers, today)
    before_fiado = before["by_payment_method"]["fiado"]
    before_efectivo = before["by_payment_method"]["efectivo"]
    before_settled = before["fiado_settled_in_range"]

    # Create pending fiado
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": marker,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200, create_res.text
    sale = create_res.json()
    amount = sale["total"]

    # After create: fiado up by amount, efectivo unchanged
    mid = _daily_summary(client, auth_headers, today)
    assert mid["by_payment_method"]["fiado"] == before_fiado + amount
    assert mid["by_payment_method"]["efectivo"] == before_efectivo

    # Settle in cash
    pay_res = client.post(
        f"/api/v1/sales/{sale['id']}/pay",
        json={"payment_method": "efectivo"},
        headers=auth_headers,
    )
    assert pay_res.status_code == 200, pay_res.text

    # After settle: fiado back down, efectivo up, fiado_settled_in_range up
    after = _daily_summary(client, auth_headers, today)
    assert after["by_payment_method"]["fiado"] == before_fiado
    assert after["by_payment_method"]["efectivo"] == before_efectivo + amount
    assert after["fiado_settled_in_range"] == before_settled + amount

    # Cleanup
    client.post(
        f"/api/v1/sales/{sale['id']}/void",
        json={"reason": marker},
        headers=auth_headers,
    )


def test_daily_summary_split_settlement_distributes(
    client, auth_headers, test_product_id, test_category_id, test_supplier_id
):
    """Fiado settled 60/40 efectivo/transferencia — each bucket gets its
    share; fiado bucket stays at its baseline."""
    today = date.today().isoformat()
    marker = f"__test_split_{int(time.time())}__"

    # Build a product whose sale_price is easy to split (1000)
    prod_res = client.post(
        "/api/v1/products",
        json={
            "name": f"{marker}_prod",
            "category_id": test_category_id,
            "supplier_id": test_supplier_id,
            "sale_price": 1000,
            "stock": 10,
            "type": "product",
        },
        headers=auth_headers,
    )
    if prod_res.status_code != 200:
        # Fallback: use the shared test product but skip if its price isn't clean
        prod = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers).json()
        prod_id = test_product_id
        price = prod["sale_price"]
        if price < 10:
            return
    else:
        prod_id = prod_res.json()["id"]
        price = 1000

    before = _daily_summary(client, auth_headers, today)
    before_fiado = before["by_payment_method"]["fiado"]
    before_efec = before["by_payment_method"]["efectivo"]
    before_trans = before["by_payment_method"]["transferencia"]

    # Create pending fiado of 1 unit
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": prod_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": marker,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200, create_res.text
    sale = create_res.json()
    total = sale["total"]
    cash_part = total * 60 // 100
    transfer_part = total - cash_part

    # Settle split
    pay_res = client.post(
        f"/api/v1/sales/{sale['id']}/pay",
        json={
            "payments": [
                {"payment_method": "efectivo", "amount": cash_part},
                {"payment_method": "transferencia", "amount": transfer_part},
            ],
        },
        headers=auth_headers,
    )
    assert pay_res.status_code == 200, pay_res.text

    after = _daily_summary(client, auth_headers, today)
    assert after["by_payment_method"]["fiado"] == before_fiado
    assert after["by_payment_method"]["efectivo"] == before_efec + cash_part
    assert after["by_payment_method"]["transferencia"] == before_trans + transfer_part

    # Cleanup
    client.post(
        f"/api/v1/sales/{sale['id']}/void",
        json={"reason": marker},
        headers=auth_headers,
    )


def test_daily_summary_voided_fiado_not_pending(
    client, auth_headers, test_product_id
):
    """Creating and voiding a fiado on the same day leaves fiado_pending
    unchanged vs the pre-test baseline."""
    today = date.today().isoformat()
    marker = f"__test_void_fiado_{int(time.time())}__"

    before = _daily_summary(client, auth_headers, today)
    before_pending = before["fiado_pending"]

    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": marker,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200, create_res.text
    sale_id = create_res.json()["id"]

    # Void it
    void_res = client.post(
        f"/api/v1/sales/{sale_id}/void",
        json={"reason": marker},
        headers=auth_headers,
    )
    assert void_res.status_code == 200, void_res.text

    after = _daily_summary(client, auth_headers, today)
    assert after["fiado_pending"] == before_pending
    assert after["by_payment_method"]["fiado"] == before_pending


def test_cash_closing_outstanding_historical(client, auth_headers):
    """total_credit_outstanding is a snapshot at end of the selected date.
    For a date far in the past with no closing saved, the value should be
    <= today's outstanding (fiados can only have been added or resolved)."""
    today = date.today().isoformat()
    old_date = (date.today() - timedelta(days=60)).isoformat()

    today_data = _cash_closing(client, auth_headers, today)
    old_data = _cash_closing(client, auth_headers, old_date)

    # Skip if either day already has a saved closing (can't re-derive)
    if today_data.get("existing") or old_data.get("existing"):
        return

    assert today_data["total_credit_outstanding"] >= old_data["total_credit_outstanding"]


def test_daily_breakdown_rows_match_range_summary(
    client, auth_headers, test_product_id
):
    """Sum of per-day total_sales over a range equals the range-level
    total_sales from daily-summary. Also verifies empty days are filled."""
    # Use a 3-day window ending today
    end_d = date.today()
    start_d = end_d - timedelta(days=2)
    params = {"date_from": start_d.isoformat(), "date_to": end_d.isoformat()}

    breakdown = client.get(
        "/api/v1/reports/daily-breakdown", params=params, headers=auth_headers
    )
    assert breakdown.status_code == 200, breakdown.text
    rows = breakdown.json()
    assert len(rows) == 3  # inclusive range of 3 days
    dates_seen = [r["date"] for r in rows]
    assert dates_seen == sorted(dates_seen)  # ascending order

    summary = client.get(
        "/api/v1/reports/daily-summary",
        params={"date": end_d.isoformat(), **params},
        headers=auth_headers,
    )
    assert summary.status_code == 200
    summary_data = summary.json()
    assert sum(r["total_sales"] for r in rows) == summary_data["total_sales"]


def test_daily_breakdown_empty_range_ok(client, auth_headers):
    """A 1-day range returns exactly one row; ancient date returns a zero row."""
    ancient = (date.today() - timedelta(days=3650)).isoformat()
    res = client.get(
        "/api/v1/reports/daily-breakdown",
        params={"date_from": ancient, "date_to": ancient},
        headers=auth_headers,
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["date"] == ancient
    assert rows[0]["total_sales"] == 0
    assert rows[0]["fiado_pending"] == 0


def test_daily_breakdown_rejects_inverted_range(client, auth_headers):
    res = client.get(
        "/api/v1/reports/daily-breakdown",
        params={"date_from": "2026-02-01", "date_to": "2026-01-01"},
        headers=auth_headers,
    )
    assert res.status_code == 400


# ── Phase 2.D tests: fiado aging as_of ──


def test_fiado_aging_default_is_snapshot(client, auth_headers):
    """Without as_of, the endpoint returns the live snapshot (backward compat)."""
    res = client.get("/api/v1/reports/fiado-aging", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_owed" in data
    assert "buckets" in data
    assert len(data["buckets"]) == 3


def test_fiado_aging_as_of_past_settles(
    client, auth_headers, test_product_id
):
    """Create a fiado, settle it. With as_of BEFORE settlement, fiado is in
    the aging total. With as_of AFTER settlement, it is not."""
    marker = f"__test_aging_asof_{int(time.time())}__"

    # Create pending fiado today
    create_res = client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": test_product_id, "quantity": 1}],
            "payment_method": "fiado",
            "client_name": marker,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 200, create_res.text
    sale = create_res.json()
    sale_id = sale["id"]
    amount = sale["total"]

    today = date.today().isoformat()

    # Before settlement: aging today includes this fiado
    before = client.get(
        "/api/v1/reports/fiado-aging",
        params={"as_of": today},
        headers=auth_headers,
    ).json()
    before_total = before["total_owed"]

    # Settle it
    pay_res = client.post(
        f"/api/v1/sales/{sale_id}/pay",
        json={"payment_method": "efectivo"},
        headers=auth_headers,
    )
    assert pay_res.status_code == 200, pay_res.text

    # After settlement: aging today excludes it
    after = client.get(
        "/api/v1/reports/fiado-aging",
        params={"as_of": today},
        headers=auth_headers,
    ).json()
    assert before_total - after["total_owed"] == amount

    # Cleanup: void the (now-completed) sale
    client.post(
        f"/api/v1/sales/{sale_id}/void",
        json={"reason": marker},
        headers=auth_headers,
    )
