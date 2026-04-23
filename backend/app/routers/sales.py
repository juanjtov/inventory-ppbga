from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import supabase
from app.auth import get_current_user, require_role
from app.models.sale import (
    SaleCreate, VoidSale, AddItemsRequest, PaySale, RemoveItemRequest,
)
from app.services.sale_service import (
    create_sale, void_sale, pay_sale, get_today_pending_fiado,
    add_items_to_sale, remove_item_from_sale, get_sale_detail,
    get_sales_summary,
)
from typing import Optional

router = APIRouter()


@router.post("")
async def create_sale_endpoint(
    sale: SaleCreate,
    user=Depends(get_current_user),
):
    result = create_sale(sale, user)
    return result


@router.get("")
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


@router.get("/summary")
async def sales_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    user=Depends(require_role("owner", "admin")),
):
    return get_sales_summary(
        date_from=date_from,
        date_to=date_to,
        status=status,
        payment_method=payment_method,
    )


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


@router.get("/pending/today")
async def pending_fiado_today(
    user=Depends(get_current_user),
):
    return get_today_pending_fiado()


@router.get("/{id}")
async def get_sale(
    id: str,
    user=Depends(require_role("owner", "admin")),
):
    try:
        sale = get_sale_detail(id)
    except Exception:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
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
    body: PaySale,
    user=Depends(require_role("owner", "admin")),
):
    result = pay_sale(id, body, user)
    return result


@router.post("/{id}/add-items")
async def add_items_endpoint(
    id: str,
    body: AddItemsRequest,
    user=Depends(get_current_user),
):
    result = add_items_to_sale(id, body, user)
    return result


@router.post("/{id}/remove-item")
async def remove_item_endpoint(
    id: str,
    body: RemoveItemRequest,
    user=Depends(require_role("owner", "admin")),
):
    return remove_item_from_sale(id, body.item_id, user)
