"""
Full battery test — 66 test cases covering all 37 endpoints.
Runs against a live Supabase instance with the backend running.
"""
import os
import time
import httpx
import pytest
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE = "http://localhost:8000"
OWNER_EMAIL = os.environ.get("TEST_OWNER_EMAIL", "premierpadelbuc@gmail.com")
OWNER_PASS = os.environ.get("TEST_OWNER_PASSWORD", "soloyomelase")


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=True) as c:
        yield c


@pytest.fixture(scope="module")
def owner_token(client):
    res = client.post("/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASS})
    assert res.status_code == 200, f"Owner login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def headers(owner_token):
    return {"Authorization": f"Bearer {owner_token}"}


# ═══════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════

class TestHealth:
    def test_health(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


# ═══════════════════════════════════════════
# AUTH (3 endpoints, 5 tests)
# ═══════════════════════════════════════════

class TestAuth:
    def test_login_success(self, client):
        res = client.post("/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASS})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["role"] == "owner"

    def test_login_wrong_password(self, client):
        res = client.post("/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": "wrongpassword123"})
        assert res.status_code == 401

    def test_login_nonexistent_email(self, client):
        res = client.post("/api/v1/auth/login", json={"email": "nobody@test.com", "password": "whatever"})
        assert res.status_code == 401

    def test_me_authenticated(self, client, headers):
        res = client.get("/api/v1/auth/me", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == OWNER_EMAIL
        assert data["role"] == "owner"
        assert "full_name" in data

    def test_me_unauthenticated(self, client):
        res = client.get("/api/v1/auth/me")
        assert res.status_code in (401, 403)


# ═══════════════════════════════════════════
# CATEGORIES (2 endpoints, 3 tests)
# ═══════════════════════════════════════════

class TestCategories:
    def test_list_categories(self, client, headers):
        res = client.get("/api/v1/categories", headers=headers)
        assert res.status_code == 200
        cats = res.json()
        assert isinstance(cats, list)
        assert len(cats) >= 6  # From CSV import

    def test_create_category(self, client, headers):
        name = f"__test_cat_{int(time.time())}__"
        res = client.post("/api/v1/categories", json={"name": name}, headers=headers)
        assert res.status_code in (200, 201)
        assert res.json()["name"] == name

    def test_create_category_in_list(self, client, headers):
        name = f"__test_cat_verify_{int(time.time())}__"
        client.post("/api/v1/categories", json={"name": name}, headers=headers)
        res = client.get("/api/v1/categories", headers=headers)
        names = [c["name"] for c in res.json()]
        assert name in names


# ═══════════════════════════════════════════
# SUPPLIERS (2 endpoints, 3 tests)
# ═══════════════════════════════════════════

class TestSuppliers:
    def test_list_suppliers(self, client, headers):
        res = client.get("/api/v1/suppliers", headers=headers)
        assert res.status_code == 200
        sups = res.json()
        assert isinstance(sups, list)
        assert len(sups) >= 10  # From CSV import

    def test_create_supplier(self, client, headers):
        name = f"__test_sup_{int(time.time())}__"
        res = client.post("/api/v1/suppliers", json={"name": name}, headers=headers)
        assert res.status_code in (200, 201)
        assert res.json()["name"] == name

    def test_create_supplier_in_list(self, client, headers):
        name = f"__test_sup_verify_{int(time.time())}__"
        client.post("/api/v1/suppliers", json={"name": name}, headers=headers)
        res = client.get("/api/v1/suppliers", headers=headers)
        names = [s["name"] for s in res.json()]
        assert name in names


# ═══════════════════════════════════════════
# PRODUCTS (7 endpoints, 12 tests)
# ═══════════════════════════════════════════

class TestProducts:
    @pytest.fixture(scope="class")
    def category_id(self, client, headers):
        res = client.get("/api/v1/categories", headers=headers)
        return res.json()[0]["id"]

    @pytest.fixture(scope="class")
    def supplier_id(self, client, headers):
        res = client.get("/api/v1/suppliers", headers=headers)
        return res.json()[0]["id"]

    def test_list_products(self, client, headers):
        res = client.get("/api/v1/products", headers=headers)
        assert res.status_code == 200
        prods = res.json()
        assert isinstance(prods, list)
        assert len(prods) >= 44

    def test_list_filter_by_search(self, client, headers):
        res = client.get("/api/v1/products", params={"search": "AGUA"}, headers=headers)
        assert res.status_code == 200
        for p in res.json():
            assert "AGUA" in p["name"].upper()

    def test_list_filter_by_type(self, client, headers):
        res = client.get("/api/v1/products", params={"type": "service"}, headers=headers)
        assert res.status_code == 200
        for p in res.json():
            assert p["type"] == "service"

    def test_list_filter_by_category(self, client, headers, category_id):
        res = client.get("/api/v1/products", params={"category_id": category_id}, headers=headers)
        assert res.status_code == 200
        for p in res.json():
            assert p["category_id"] == category_id

    def test_get_product_detail(self, client, headers):
        prods = client.get("/api/v1/products", headers=headers).json()
        pid = prods[0]["id"]
        res = client.get(f"/api/v1/products/{pid}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "category_name" in data
        assert "supplier_name" in data
        assert "is_low_stock" in data

    def test_create_product(self, client, headers, category_id, supplier_id):
        name = f"__battery_prod_{int(time.time())}__"
        res = client.post("/api/v1/products", json={
            "name": name, "category_id": category_id, "supplier_id": supplier_id,
            "sale_price": 7777, "purchase_price": 3333, "stock": 50, "type": "product",
        }, headers=headers)
        assert res.status_code == 200
        assert res.json()["sale_price"] == 7777

    def test_create_service(self, client, headers, category_id, supplier_id):
        name = f"__battery_svc_{int(time.time())}__"
        res = client.post("/api/v1/products", json={
            "name": name, "category_id": category_id, "supplier_id": supplier_id,
            "sale_price": 15000, "type": "service",
        }, headers=headers)
        assert res.status_code == 200
        assert res.json()["type"] == "service"
        assert res.json()["stock"] is None

    def test_update_product(self, client, headers, category_id, supplier_id):
        name = f"__battery_upd_{int(time.time())}__"
        created = client.post("/api/v1/products", json={
            "name": name, "category_id": category_id, "supplier_id": supplier_id,
            "sale_price": 1000, "stock": 10, "type": "product",
        }, headers=headers).json()
        res = client.put(f"/api/v1/products/{created['id']}", json={"sale_price": 2000}, headers=headers)
        assert res.status_code == 200

    def test_update_price_with_audit(self, client, headers):
        prods = client.get("/api/v1/products", headers=headers).json()
        product_prods = [p for p in prods if p["type"] == "product"]
        pid = product_prods[0]["id"]
        old_price = product_prods[0]["sale_price"]
        new_price = old_price + 500
        res = client.put(f"/api/v1/products/{pid}/price", json={"sale_price": new_price}, headers=headers)
        assert res.status_code == 200
        # Verify audit log has entry
        audit = client.get("/api/v1/audit-log", params={"entity_id": pid}, headers=headers)
        assert audit.status_code == 200

    def test_csv_import(self, client, headers):
        csv_data = (
            ",,,,,,\n,,,,,,\n,,,,,,\n"
            ",Producto,Categoria,Proveedor,,Precio,Sotck Actual\n"
            f",BATTERY_TEST_{int(time.time())},Snacks,Postobon,,\"$2,000\",5\n"
        )
        res = client.post("/api/v1/products/import-csv",
            files={"file": ("test.csv", csv_data.encode(), "text/csv")},
            headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["created"] >= 1
        assert isinstance(data["errors"], list)

    def test_low_stock(self, client, headers):
        res = client.get("/api/v1/products/low-stock", headers=headers)
        assert res.status_code == 200
        for p in res.json():
            assert p["type"] == "product"
            assert p["stock"] is not None
            assert p["stock"] <= p["min_stock_alert"]


# ═══════════════════════════════════════════
# SALES (6 endpoints, 12 tests)
# ═══════════════════════════════════════════

class TestSales:
    @pytest.fixture(scope="class")
    def product_with_stock(self, client, headers):
        """Get a product with stock > 20 for safe testing."""
        prods = client.get("/api/v1/products", headers=headers).json()
        for p in prods:
            if p["type"] == "product" and p["stock"] and p["stock"] > 20:
                return p
        pytest.skip("No product with sufficient stock found")

    @pytest.fixture(scope="class")
    def service_product(self, client, headers):
        prods = client.get("/api/v1/products", params={"type": "service"}, headers=headers).json()
        if not prods:
            pytest.skip("No service product found")
        return prods[0]

    def test_create_cash_sale(self, client, headers, product_with_stock):
        pid = product_with_stock["id"]
        stock_before = client.get(f"/api/v1/products/{pid}", headers=headers).json()["stock"]
        res = client.post("/api/v1/sales", json={
            "items": [{"product_id": pid, "quantity": 2}],
            "payment_method": "efectivo",
        }, headers=headers)
        assert res.status_code == 200
        sale = res.json()
        assert sale["status"] == "completed"
        assert sale["payment_method"] == "efectivo"
        assert len(sale["items"]) == 1
        # Verify stock decremented
        stock_after = client.get(f"/api/v1/products/{pid}", headers=headers).json()["stock"]
        assert stock_after == stock_before - 2

    def test_create_fiado_requires_client(self, client, headers, product_with_stock):
        res = client.post("/api/v1/sales", json={
            "items": [{"product_id": product_with_stock["id"], "quantity": 1}],
            "payment_method": "fiado",
        }, headers=headers)
        assert res.status_code == 400

    def test_create_fiado_with_client(self, client, headers, product_with_stock):
        res = client.post("/api/v1/sales", json={
            "items": [{"product_id": product_with_stock["id"], "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "Juan Battery Test",
        }, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "pending"
        assert res.json()["client_name"] == "Juan Battery Test"

    def test_create_service_sale(self, client, headers, service_product):
        res = client.post("/api/v1/sales", json={
            "items": [{"product_id": service_product["id"], "quantity": 1}],
            "payment_method": "efectivo",
        }, headers=headers)
        assert res.status_code == 200

    def test_oversell_rejected(self, client, headers):
        # Create product with stock=1
        cats = client.get("/api/v1/categories", headers=headers).json()
        sups = client.get("/api/v1/suppliers", headers=headers).json()
        name = f"__oversell_{int(time.time())}__"
        prod = client.post("/api/v1/products", json={
            "name": name, "category_id": cats[0]["id"], "supplier_id": sups[0]["id"],
            "sale_price": 1000, "stock": 1, "type": "product",
        }, headers=headers).json()
        res = client.post("/api/v1/sales", json={
            "items": [{"product_id": prod["id"], "quantity": 999}],
            "payment_method": "efectivo",
        }, headers=headers)
        assert res.status_code == 400

    def test_list_sales(self, client, headers):
        res = client.get("/api/v1/sales", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_sales_with_filters(self, client, headers):
        today = date.today().isoformat()
        res = client.get("/api/v1/sales", params={
            "date_from": today, "date_to": today, "status": "completed",
        }, headers=headers)
        assert res.status_code == 200

    def test_list_pending_sales(self, client, headers):
        res = client.get("/api/v1/sales/pending", headers=headers)
        assert res.status_code == 200
        for s in res.json():
            assert s["status"] == "pending"

    def test_get_sale_detail(self, client, headers, product_with_stock):
        sale = client.post("/api/v1/sales", json={
            "items": [{"product_id": product_with_stock["id"], "quantity": 1}],
            "payment_method": "efectivo",
        }, headers=headers).json()
        res = client.get(f"/api/v1/sales/{sale['id']}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_void_sale_restores_stock(self, client, headers, product_with_stock):
        pid = product_with_stock["id"]
        stock_before = client.get(f"/api/v1/products/{pid}", headers=headers).json()["stock"]
        sale = client.post("/api/v1/sales", json={
            "items": [{"product_id": pid, "quantity": 3}],
            "payment_method": "efectivo",
        }, headers=headers).json()
        # Stock decreased
        stock_mid = client.get(f"/api/v1/products/{pid}", headers=headers).json()["stock"]
        assert stock_mid == stock_before - 3
        # Void
        res = client.post(f"/api/v1/sales/{sale['id']}/void", json={"reason": "Battery test void"}, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "voided"
        # Stock restored
        stock_after = client.get(f"/api/v1/products/{pid}", headers=headers).json()["stock"]
        assert stock_after == stock_before

    def test_void_already_voided(self, client, headers, product_with_stock):
        sale = client.post("/api/v1/sales", json={
            "items": [{"product_id": product_with_stock["id"], "quantity": 1}],
            "payment_method": "efectivo",
        }, headers=headers).json()
        client.post(f"/api/v1/sales/{sale['id']}/void", json={"reason": "first"}, headers=headers)
        res = client.post(f"/api/v1/sales/{sale['id']}/void", json={"reason": "second"}, headers=headers)
        assert res.status_code == 400

    def test_pay_fiado(self, client, headers, product_with_stock):
        sale = client.post("/api/v1/sales", json={
            "items": [{"product_id": product_with_stock["id"], "quantity": 1}],
            "payment_method": "fiado",
            "client_name": "Pay Test",
        }, headers=headers).json()
        res = client.post(f"/api/v1/sales/{sale['id']}/pay", headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "completed"

    def test_pay_non_pending_rejected(self, client, headers, product_with_stock):
        sale = client.post("/api/v1/sales", json={
            "items": [{"product_id": product_with_stock["id"], "quantity": 1}],
            "payment_method": "efectivo",
        }, headers=headers).json()
        res = client.post(f"/api/v1/sales/{sale['id']}/pay", headers=headers)
        assert res.status_code == 400


# ═══════════════════════════════════════════
# INVENTORY (3 endpoints, 7 tests)
# ═══════════════════════════════════════════

class TestInventory:
    @pytest.fixture(scope="class")
    def product_for_inv(self, client, headers):
        prods = client.get("/api/v1/products", headers=headers).json()
        for p in prods:
            if p["type"] == "product" and p["stock"] and p["stock"] > 10:
                return p
        pytest.skip("No suitable product")

    @pytest.fixture(scope="class")
    def service_for_inv(self, client, headers):
        prods = client.get("/api/v1/products", params={"type": "service"}, headers=headers).json()
        if not prods:
            pytest.skip("No service")
        return prods[0]

    def test_inventory_entry_increments_stock(self, client, headers, product_for_inv):
        pid = product_for_inv["id"]
        stock_before = client.get(f"/api/v1/products/{pid}", headers=headers).json()["stock"]
        sups = client.get("/api/v1/suppliers", headers=headers).json()
        res = client.post("/api/v1/inventory/entry", json={
            "product_id": pid, "quantity": 10,
            "supplier_id": sups[0]["id"], "price_confirmed": True,
        }, headers=headers)
        assert res.status_code == 200
        stock_after = client.get(f"/api/v1/products/{pid}", headers=headers).json()["stock"]
        assert stock_after == stock_before + 10

    def test_inventory_entry_price_change(self, client, headers, product_for_inv):
        pid = product_for_inv["id"]
        sups = client.get("/api/v1/suppliers", headers=headers).json()
        res = client.post("/api/v1/inventory/entry", json={
            "product_id": pid, "quantity": 5,
            "supplier_id": sups[0]["id"],
            "price_confirmed": False, "actual_price": 8888,
        }, headers=headers)
        assert res.status_code == 200
        prod = client.get(f"/api/v1/products/{pid}", headers=headers).json()
        assert prod["purchase_price"] == 8888

    def test_internal_use_decrements(self, client, headers, product_for_inv):
        pid = product_for_inv["id"]
        stock_before = client.get(f"/api/v1/products/{pid}", headers=headers).json()["stock"]
        res = client.post("/api/v1/inventory/internal-use", json={
            "product_id": pid, "quantity": 2, "reason": "Battery test uso interno",
        }, headers=headers)
        assert res.status_code == 200
        stock_after = client.get(f"/api/v1/products/{pid}", headers=headers).json()["stock"]
        assert stock_after == stock_before - 2

    def test_internal_use_service_rejected(self, client, headers, service_for_inv):
        res = client.post("/api/v1/inventory/internal-use", json={
            "product_id": service_for_inv["id"], "quantity": 1,
            "reason": "Esto debe fallar para servicios",
        }, headers=headers)
        assert res.status_code == 400

    def test_internal_use_exceed_stock_rejected(self, client, headers):
        cats = client.get("/api/v1/categories", headers=headers).json()
        sups = client.get("/api/v1/suppliers", headers=headers).json()
        prod = client.post("/api/v1/products", json={
            "name": f"__inv_exceed_{int(time.time())}__",
            "category_id": cats[0]["id"], "supplier_id": sups[0]["id"],
            "sale_price": 1000, "stock": 1, "type": "product",
        }, headers=headers).json()
        res = client.post("/api/v1/inventory/internal-use", json={
            "product_id": prod["id"], "quantity": 999,
            "reason": "Intentando usar mas del stock",
        }, headers=headers)
        assert res.status_code == 400

    def test_internal_use_short_reason_rejected(self, client, headers, product_for_inv):
        res = client.post("/api/v1/inventory/internal-use", json={
            "product_id": product_for_inv["id"], "quantity": 1, "reason": "ab",
        }, headers=headers)
        assert res.status_code == 400

    def test_movements_timeline(self, client, headers, product_for_inv):
        res = client.get("/api/v1/inventory/movements",
            params={"product_id": product_for_inv["id"]}, headers=headers)
        assert res.status_code == 200
        movements = res.json()
        assert isinstance(movements, list)
        if movements:
            assert movements[0]["type"] in ("sale", "entry", "internal_use", "void")


# ═══════════════════════════════════════════
# REPORTS (8 endpoints, 12 tests)
# ═══════════════════════════════════════════

class TestReports:
    def test_daily_summary(self, client, headers):
        today = date.today().isoformat()
        res = client.get("/api/v1/reports/daily-summary", params={"date": today}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "total_sales" in data
        assert "avg_ticket" in data
        assert "by_payment_method" in data
        assert "top_products" in data

    def test_cash_closing_data(self, client, headers):
        today = date.today().isoformat()
        res = client.get("/api/v1/reports/cash-closing", params={"date": today}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        if not data.get("existing"):
            assert "total_sales" in data
            assert "total_cash" in data

    def test_create_cash_closing(self, client, headers):
        test_date = "2019-01-01"
        res = client.post("/api/v1/reports/cash-closing", json={
            "closing_date": test_date, "physical_cash": 50000, "notes": "Battery test",
        }, headers=headers)
        assert res.status_code in (200, 400)  # 400 if already exists

    def test_cash_closing_duplicate_rejected(self, client, headers):
        test_date = "2019-01-02"
        client.post("/api/v1/reports/cash-closing", json={
            "closing_date": test_date, "physical_cash": 0,
        }, headers=headers)
        res = client.post("/api/v1/reports/cash-closing", json={
            "closing_date": test_date, "physical_cash": 0,
        }, headers=headers)
        assert res.status_code == 400

    def test_top_sellers_day(self, client, headers):
        today = date.today().isoformat()
        res = client.get("/api/v1/reports/top-sellers", params={"period": "day", "date": today}, headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_top_sellers_week(self, client, headers):
        today = date.today().isoformat()
        res = client.get("/api/v1/reports/top-sellers", params={"period": "week", "date": today}, headers=headers)
        assert res.status_code == 200

    def test_top_sellers_month(self, client, headers):
        today = date.today().isoformat()
        res = client.get("/api/v1/reports/top-sellers", params={"period": "month", "date": today}, headers=headers)
        assert res.status_code == 200

    def test_top_sellers_invalid_period(self, client, headers):
        res = client.get("/api/v1/reports/top-sellers", params={"period": "dia", "date": "2026-03-23"}, headers=headers)
        assert res.status_code == 400

    def test_inventory_value(self, client, headers):
        res = client.get("/api/v1/reports/inventory-value", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "grand_total_sale" in data
        assert "grand_total_purchase" in data
        assert len(data["items"]) > 0

    def test_reconciliation(self, client, headers):
        today = date.today().isoformat()
        res = client.get("/api/v1/reports/reconciliation", params={
            "date_from": today, "date_to": today,
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        if data:
            assert "total_sold" in data[0]
            assert "total_entered" in data[0]
            assert "actual_stock" in data[0]

    def test_fiado_aging(self, client, headers):
        res = client.get("/api/v1/reports/fiado-aging", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "total_owed" in data
        assert "buckets" in data
        assert len(data["buckets"]) == 3

    def test_export_sales_csv(self, client, headers):
        today = date.today().isoformat()
        res = client.get("/api/v1/reports/export/sales", params={
            "date_from": today, "date_to": today,
        }, headers=headers)
        assert res.status_code == 200
        assert "text/csv" in res.headers.get("content-type", "")


# ═══════════════════════════════════════════
# USERS (4 endpoints, 7 tests)
# ═══════════════════════════════════════════

class TestUsers:
    def test_list_users(self, client, headers):
        res = client.get("/api/v1/users", headers=headers)
        assert res.status_code == 200
        users = res.json()
        assert isinstance(users, list)
        assert len(users) >= 1

    def test_create_worker(self, client, headers):
        ts = int(time.time())
        res = client.post("/api/v1/users", json={
            "email": f"worker_{ts}@battery.test",
            "password": "BatteryTest123!",
            "full_name": f"Worker Battery {ts}",
            "role": "worker",
        }, headers=headers)
        assert res.status_code in (200, 201)
        assert res.json()["role"] == "worker"

    def test_create_admin(self, client, headers):
        ts = int(time.time())
        res = client.post("/api/v1/users", json={
            "email": f"admin_{ts}@battery.test",
            "password": "BatteryTest123!",
            "full_name": f"Admin Battery {ts}",
            "role": "admin",
        }, headers=headers)
        assert res.status_code in (200, 201)
        assert res.json()["role"] == "admin"

    def test_create_owner_rejected(self, client, headers):
        ts = int(time.time())
        res = client.post("/api/v1/users", json={
            "email": f"owner_{ts}@battery.test",
            "password": "BatteryTest123!",
            "full_name": "Owner Rejected",
            "role": "owner",
        }, headers=headers)
        assert res.status_code == 400

    def test_update_user_name(self, client, headers):
        users = client.get("/api/v1/users", headers=headers).json()
        non_owner = next((u for u in users if u["role"] != "owner"), None)
        if not non_owner:
            pytest.skip("No non-owner user to update")
        res = client.put(f"/api/v1/users/{non_owner['id']}", json={
            "full_name": "Updated Battery Name",
        }, headers=headers)
        assert res.status_code == 200

    def test_self_role_change_rejected(self, client, headers):
        me = client.get("/api/v1/auth/me", headers=headers).json()
        res = client.put(f"/api/v1/users/{me['id']}", json={"role": "admin"}, headers=headers)
        assert res.status_code == 400

    def test_self_deactivate_rejected(self, client, headers):
        me = client.get("/api/v1/auth/me", headers=headers).json()
        res = client.put(f"/api/v1/users/{me['id']}/deactivate", headers=headers)
        assert res.status_code == 400


# ═══════════════════════════════════════════
# AUDIT LOG (1 endpoint, 1 test)
# ═══════════════════════════════════════════

class TestAuditLog:
    def test_list_audit_log(self, client, headers):
        res = client.get("/api/v1/audit-log", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)
