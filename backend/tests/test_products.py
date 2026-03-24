"""Products endpoint tests."""


def test_list_products(client, auth_headers):
    res = client.get("/api/v1/products", headers=auth_headers)
    assert res.status_code == 200
    products = res.json()
    assert isinstance(products, list)


def test_list_products_with_search(client, auth_headers, test_product_id):
    res = client.get(
        "/api/v1/products", params={"search": "__test_product__"}, headers=auth_headers
    )
    assert res.status_code == 200
    products = res.json()
    assert any(p["name"] == "__test_product__" for p in products)


def test_list_products_with_type_filter(client, auth_headers):
    res = client.get(
        "/api/v1/products", params={"type": "service"}, headers=auth_headers
    )
    assert res.status_code == 200
    for p in res.json():
        assert p["type"] == "service"


def test_get_product(client, auth_headers, test_product_id):
    res = client.get(f"/api/v1/products/{test_product_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == test_product_id
    assert "category_name" in data
    assert "supplier_name" in data
    assert "is_low_stock" in data


def test_create_product(client, auth_headers, test_category_id, test_supplier_id):
    res = client.post(
        "/api/v1/products",
        json={
            "name": f"__test_product_create_{id(test_category_id)}__",
            "category_id": test_category_id,
            "supplier_id": test_supplier_id,
            "sale_price": 8000,
            "purchase_price": 4000,
            "stock": 50,
            "type": "product",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sale_price"] == 8000


def test_update_product_price(client, auth_headers, test_product_id):
    res = client.put(
        f"/api/v1/products/{test_product_id}/price",
        json={"sale_price": 6000},
        headers=auth_headers,
    )
    assert res.status_code == 200


def test_low_stock_products(client, auth_headers):
    res = client.get("/api/v1/products/low-stock", headers=auth_headers)
    assert res.status_code == 200
    products = res.json()
    assert isinstance(products, list)
    for p in products:
        assert p["type"] == "product"
        assert p["stock"] is not None
        assert p["stock"] <= p["min_stock_alert"]


def test_csv_import(client, auth_headers):
    csv_content = (
        ",,,,,,\n"
        ",,,,,,\n"
        ",,,,,,\n"
        ",Producto,Categoria,Proveedor,,Precio,Sotck Actual\n"
        ",CSV_TEST_PRODUCT,__csv_test_cat__,__csv_test_sup__,,\"$5,500\",10\n"
        ",CSV_TEST_SERVICE,__csv_test_cat__,__csv_test_sup__,,\"$10,000\",NA\n"
    )
    res = client.post(
        "/api/v1/products/import-csv",
        files={"file": ("test.csv", csv_content.encode(), "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "created" in data
    assert "skipped" in data
    assert "errors" in data
