from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import supabase
from app.auth import get_current_user, require_role
from app.models.sale import SaleCreate, VoidSale
from app.services.sale_service import create_sale, void_sale, pay_sale
from typing import Optional

router = APIRouter()


@router.post("/")
async def create_sale_endpoint(
    sale: SaleCreate,
    user=Depends(get_current_user),
):
    result = create_sale(sale, user)
    return result


@router.get("/")
async def list_sales(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    limit: int = Query(default=20),
    offset: int = Query(default=0),
    user=Depends(require_role("owner", "admin")),
):
    query = supabase.table("sales").select(
        "*, users!sales_user_id_fkey(full_name)"
    ).order("created_at", desc=True)

    if date_from:
        query = query.gte("created_at", f"{date_from}T00:00:00-05:00")
    if date_to:
        query = query.lte("created_at", f"{date_to}T23:59:59-05:00")
    if status:
        query = query.eq("status", status)
    if payment_method:
        query = query.eq("payment_method", payment_method)

    query = query.range(offset, offset + limit - 1)
    result = query.execute()

    sales = []
    for s in result.data:
        s["user_name"] = (s.pop("users", {}) or {}).get("full_name")
        sales.append(s)

    return sales


@router.get("/pending")
async def pending_sales(
    user=Depends(require_role("owner", "admin")),
):
    result = (
        supabase.table("sales")
        .select("*, users!sales_user_id_fkey(full_name)")
        .eq("payment_method", "fiado")
        .in_("status", ["pending", "completed"])
        .order("created_at", desc=False)
        .execute()
    )

    sales = []
    for s in result.data:
        s["user_name"] = (s.pop("users", {}) or {}).get("full_name")
        sales.append(s)

    # Pending first, then completed (paid) at the bottom
    sales.sort(key=lambda s: (0 if s["status"] == "pending" else 1, s["created_at"]))

    return sales


@router.get("/{id}")
async def get_sale(
    id: str,
    user=Depends(require_role("owner", "admin")),
):
    try:
        result = (
            supabase.table("sales")
            .select("*, users!sales_user_id_fkey(full_name)")
            .eq("id", id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    if not result.data:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    sale = result.data
    sale["user_name"] = (sale.pop("users", {}) or {}).get("full_name")

    items_result = (
        supabase.table("sale_items")
        .select("*, products(name)")
        .eq("sale_id", id)
        .execute()
    )

    items = []
    for item in items_result.data:
        item["product_name"] = (item.pop("products", {}) or {}).get("name")
        items.append(item)

    sale["items"] = items

    return sale


@router.post("/{id}/void")
async def void_sale_endpoint(
    id: str,
    body: VoidSale,
    user=Depends(require_role("owner", "admin")),
):
    result = void_sale(id, body.reason, user)
    return result


@router.post("/{id}/pay")
async def pay_sale_endpoint(
    id: str,
    user=Depends(require_role("owner", "admin")),
):
    result = pay_sale(id, user)
    return result
