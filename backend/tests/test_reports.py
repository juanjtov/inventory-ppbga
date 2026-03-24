"""Reports endpoint tests."""
from datetime import date


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
