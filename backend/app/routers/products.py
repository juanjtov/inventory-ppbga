from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from app.database import supabase
from app.auth import get_current_user, require_role
from app.models.product import ProductCreate, ProductUpdate, PriceUpdate
from app.services.csv_import_service import import_csv
from typing import Optional

router = APIRouter()


@router.get("")
async def list_products(
    category_id: Optional[str] = None,
    search: Optional[str] = None,
    type: Optional[str] = None,
    user=Depends(get_current_user),
):
    query = supabase.table("products").select(
        "*, categories(name), suppliers(name)"
    ).eq("is_active", True)

    if category_id:
        query = query.eq("category_id", category_id)
    if search:
        query = query.ilike("name", f"%{search}%")
    if type:
        query = query.eq("type", type)

    result = query.execute()

    products = []
    for p in result.data:
        p["category_name"] = (
            p.pop("categories", {}) or {}
        ).get("name")
        p["supplier_name"] = (
            p.pop("suppliers", {}) or {}
        ).get("name")
        p["is_low_stock"] = (
            p["stock"] is not None and p["stock"] <= p["min_stock_alert"]
        )
        products.append(p)

    return products


@router.get("/low-stock")
async def low_stock_products(
    user=Depends(require_role("owner", "admin")),
):
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
            p["category_name"] = (
                p.pop("categories", {}) or {}
            ).get("name")
            p["supplier_name"] = (
                p.pop("suppliers", {}) or {}
            ).get("name")
            p["is_low_stock"] = True
            products.append(p)

    return products


@router.get("/{id}")
async def get_product(id: str, user=Depends(get_current_user)):
    try:
        result = (
            supabase.table("products")
            .select("*, categories(name), suppliers(name)")
            .eq("id", id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if not result.data:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    p = result.data
    p["category_name"] = (p.pop("categories", {}) or {}).get("name")
    p["supplier_name"] = (p.pop("suppliers", {}) or {}).get("name")
    p["is_low_stock"] = (
        p["stock"] is not None and p["stock"] <= p["min_stock_alert"]
    )

    return p


@router.post("")
async def create_product(
    product: ProductCreate,
    user=Depends(require_role("owner", "admin")),
):
    data = product.model_dump()

    if data["type"] == "service":
        data["stock"] = None

    result = supabase.table("products").insert(data).execute()

    if not result.data:
        raise HTTPException(
            status_code=400, detail="Error al crear el producto"
        )

    return result.data[0]


@router.put("/{id}")
async def update_product(
    id: str,
    product: ProductUpdate,
    user=Depends(require_role("owner")),
):
    data = product.model_dump(exclude_unset=True)

    if not data:
        raise HTTPException(
            status_code=400, detail="No se enviaron datos para actualizar"
        )

    result = (
        supabase.table("products").update(data).eq("id", id).execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return result.data[0]


@router.put("/{id}/price")
async def update_price(
    id: str,
    body: PriceUpdate,
    user=Depends(require_role("owner")),
):
    current = (
        supabase.table("products")
        .select("sale_price")
        .eq("id", id)
        .single()
        .execute()
    )

    if not current.data:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    old_price = current.data["sale_price"]

    result = (
        supabase.table("products")
        .update({"sale_price": body.sale_price})
        .eq("id", id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=400, detail="Error al actualizar el precio"
        )

    supabase.table("audit_log").insert({
        "action": "price_change",
        "entity_type": "product",
        "entity_id": id,
        "old_values": {"sale_price": old_price},
        "new_values": {"sale_price": body.sale_price},
        "user_id": user["id"],
    }).execute()

    return result.data[0]


@router.post("/import-csv")
async def import_csv_endpoint(
    file: UploadFile = File(...),
    user=Depends(require_role("owner")),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400, detail="El archivo debe ser un CSV"
        )

    content = await file.read()
    result = import_csv(content)

    return result


@router.delete("/{id}")
async def delete_product(
    id: str,
    user=Depends(require_role("owner")),
):
    # Check product exists
    try:
        product = (
            supabase.table("products")
            .select("id, name")
            .eq("id", id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if not product.data:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Check if product has sale_items (FK constraint)
    sale_items = (
        supabase.table("sale_items")
        .select("id")
        .eq("product_id", id)
        .limit(1)
        .execute()
    )
    if sale_items.data:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar un producto con ventas registradas. Desactivelo en su lugar.",
        )

    # Delete related records (inventory_entries, internal_use, audit_log)
    supabase.table("audit_log").delete().eq("entity_id", id).execute()
    supabase.table("inventory_entries").delete().eq("product_id", id).execute()
    supabase.table("internal_use").delete().eq("product_id", id).execute()

    # Delete the product
    try:
        supabase.table("products").delete().eq("id", id).execute()
    except Exception:
        raise HTTPException(
            status_code=400, detail="Error al eliminar el producto"
        )

    return {"message": f"Producto '{product.data['name']}' eliminado correctamente"}
