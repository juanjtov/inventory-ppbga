from fastapi import HTTPException
from app.database import supabase
from app.models.stock_adjustment import StockAdjustmentCreate
from app.timezone import col_now


def create_adjustment(data: StockAdjustmentCreate, user: dict) -> dict:
    """Record a physical stock count and snap products.stock to the counted
    value. Captures the before/after on a stock_adjustments row and writes
    an audit log entry."""
    if data.counted_quantity < 0:
        raise HTTPException(
            status_code=400,
            detail="La cantidad contada no puede ser negativa",
        )

    product = (
        supabase.table("products")
        .select("id, name, stock, type, is_active")
        .eq("id", data.product_id)
        .single()
        .execute()
    )
    if not product.data:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    p = product.data
    if p["type"] != "product":
        raise HTTPException(
            status_code=400,
            detail="Solo los productos con stock pueden ajustarse",
        )

    # Capture the pre-adjustment value. Nullable in schema — treat as 0.
    system_quantity = p["stock"] if p["stock"] is not None else 0
    difference = data.counted_quantity - system_quantity

    # Atomic update via set_stock RPC (migration 006). Returns old stock;
    # we've already captured it above for the audit row.
    supabase.rpc(
        "set_stock",
        {"p_product_id": data.product_id, "p_new_value": data.counted_quantity},
    ).execute()

    # Persist adjustment record
    now_iso = col_now().isoformat()
    row = {
        "product_id": data.product_id,
        "counted_quantity": data.counted_quantity,
        "system_quantity": system_quantity,
        "difference": difference,
        "reason": data.reason,
        "adjusted_by": user["id"],
        "adjusted_at": now_iso,
    }
    result = supabase.table("stock_adjustments").insert(row).execute()

    # Audit log
    supabase.table("audit_log").insert({
        "user_id": user["id"],
        "action": "stock_adjustment",
        "entity_type": "product",
        "entity_id": data.product_id,
        "old_values": {"stock": system_quantity},
        "new_values": {
            "stock": data.counted_quantity,
            "difference": difference,
            "reason": data.reason,
        },
    }).execute()

    return result.data[0]


def list_adjustments(
    product_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
) -> list:
    query = (
        supabase.table("stock_adjustments")
        .select("*, products(name), users!stock_adjustments_adjusted_by_fkey(full_name)")
        .order("adjusted_at", desc=True)
        .limit(limit)
    )
    if product_id:
        query = query.eq("product_id", product_id)
    if date_from:
        query = query.gte("adjusted_at", f"{date_from}T00:00:00-05:00")
    if date_to:
        query = query.lte("adjusted_at", f"{date_to}T23:59:59-05:00")
    result = query.execute()
    rows = []
    for r in result.data or []:
        r["product_name"] = (r.pop("products", {}) or {}).get("name")
        r["user_name"] = (r.pop("users", {}) or {}).get("full_name")
        rows.append(r)
    return rows
