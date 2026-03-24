from app.database import supabase
from typing import Optional


def get_products(
    category_id: Optional[str] = None,
    search: Optional[str] = None,
    product_type: Optional[str] = None,
):
    query = (
        supabase.table("products")
        .select("*, categories(name), suppliers(name)")
        .eq("is_active", True)
    )

    if category_id:
        query = query.eq("category_id", category_id)
    if product_type:
        query = query.eq("type", product_type)
    if search:
        query = query.ilike("name", f"%{search}%")

    result = query.order("name").execute()

    products = []
    for p in result.data:
        p["category_name"] = p.get("categories", {}).get("name") if p.get("categories") else None
        p["supplier_name"] = p.get("suppliers", {}).get("name") if p.get("suppliers") else None
        # Compute is_low_stock
        if p["type"] == "product" and p["stock"] is not None:
            p["is_low_stock"] = p["stock"] <= p["min_stock_alert"]
        else:
            p["is_low_stock"] = False
        # Clean up nested objects
        p.pop("categories", None)
        p.pop("suppliers", None)
        products.append(p)

    return products


def get_product(product_id: str):
    result = (
        supabase.table("products")
        .select("*, categories(name), suppliers(name)")
        .eq("id", product_id)
        .single()
        .execute()
    )
    if not result.data:
        return None
    p = result.data
    p["category_name"] = p.get("categories", {}).get("name") if p.get("categories") else None
    p["supplier_name"] = p.get("suppliers", {}).get("name") if p.get("suppliers") else None
    if p["type"] == "product" and p["stock"] is not None:
        p["is_low_stock"] = p["stock"] <= p["min_stock_alert"]
    else:
        p["is_low_stock"] = False
    p.pop("categories", None)
    p.pop("suppliers", None)
    return p


def get_low_stock_products():
    result = (
        supabase.table("products")
        .select("*, categories(name), suppliers(name)")
        .eq("is_active", True)
        .eq("type", "product")
        .execute()
    )

    products = []
    for p in result.data:
        if p["stock"] is not None and p["stock"] <= p["min_stock_alert"]:
            p["category_name"] = p.get("categories", {}).get("name") if p.get("categories") else None
            p["supplier_name"] = p.get("suppliers", {}).get("name") if p.get("suppliers") else None
            p["is_low_stock"] = True
            p.pop("categories", None)
            p.pop("suppliers", None)
            products.append(p)

    return products
