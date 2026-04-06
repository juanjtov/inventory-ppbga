from fastapi import HTTPException
from app.database import supabase
from app.models.sale import SaleCreate, AddItemsRequest, PaySale
from app.timezone import col_now, date_range_col


VALID_PAY_METHODS = {"efectivo", "datafono", "transferencia"}


def create_sale(data: SaleCreate, user: dict) -> dict:
    """Create a sale with atomic stock decrement."""
    # Validate fiado requires client_name
    if data.payment_method == "fiado" and not data.client_name:
        raise HTTPException(
            status_code=400,
            detail="El nombre del cliente es obligatorio para ventas a fiado",
        )

    # Validate all items and compute totals
    items_data = []
    total = 0

    for item in data.items:
        product = (
            supabase.table("products")
            .select("*")
            .eq("id", item.product_id)
            .single()
            .execute()
        )
        if not product.data:
            raise HTTPException(
                status_code=404,
                detail=f"Producto no encontrado: {item.product_id}",
            )
        p = product.data

        # Check stock for products (not services)
        if p["type"] == "product":
            if p["stock"] is None or p["stock"] < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para '{p['name']}'. Disponible: {p.get('stock', 0)}, solicitado: {item.quantity}",
                )

        subtotal = p["sale_price"] * item.quantity
        items_data.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "unit_price": p["sale_price"],
            "subtotal": subtotal,
            "product_type": p["type"],
        })
        total += subtotal

    # Determine status
    status = "pending" if data.payment_method == "fiado" else "completed"

    # Insert sale
    sale_data = {
        "user_id": user["id"],
        "total": total,
        "payment_method": data.payment_method,
        "status": status,
        "client_name": data.client_name,
        "notes": data.notes,
    }
    sale_result = supabase.table("sales").insert(sale_data).execute()
    sale = sale_result.data[0]

    # Insert sale items and decrement stock
    for item_data in items_data:
        sale_item = {
            "sale_id": sale["id"],
            "product_id": item_data["product_id"],
            "quantity": item_data["quantity"],
            "unit_price": item_data["unit_price"],
            "subtotal": item_data["subtotal"],
        }
        supabase.table("sale_items").insert(sale_item).execute()

        # Decrement stock for products (not services)
        if item_data["product_type"] == "product":
            # Atomic decrement using RPC or direct update
            product = (
                supabase.table("products")
                .select("stock")
                .eq("id", item_data["product_id"])
                .single()
                .execute()
            )
            new_stock = product.data["stock"] - item_data["quantity"]
            if new_stock < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente (condición de carrera detectada)",
                )
            supabase.table("products").update({"stock": new_stock}).eq(
                "id", item_data["product_id"]
            ).execute()

    # Fetch complete sale with items
    return get_sale_detail(sale["id"])


def get_today_pending_fiado() -> list:
    """Get today's pending fiado sales for the POS dropdown."""
    today_str = col_now().strftime("%Y-%m-%d")
    date_start, date_end = date_range_col(today_str)

    result = (
        supabase.table("sales")
        .select("id, client_name, total")
        .eq("status", "pending")
        .eq("payment_method", "fiado")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .order("client_name", desc=False)
        .execute()
    )
    return result.data


def add_items_to_sale(sale_id: str, data: AddItemsRequest, user: dict) -> dict:
    """Add items to an existing pending fiado sale."""
    # Fetch and validate the sale
    try:
        sale = (
            supabase.table("sales")
            .select("*")
            .eq("id", sale_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    if not sale.data:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    if sale.data["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden agregar items a ventas pendientes",
        )

    if sale.data["payment_method"] != "fiado":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden agregar items a ventas fiado",
        )

    # Validate items and compute totals (same pattern as create_sale)
    items_data = []
    added_total = 0

    for item in data.items:
        product = (
            supabase.table("products")
            .select("*")
            .eq("id", item.product_id)
            .single()
            .execute()
        )
        if not product.data:
            raise HTTPException(
                status_code=404,
                detail=f"Producto no encontrado: {item.product_id}",
            )
        p = product.data

        if p["type"] == "product":
            if p["stock"] is None or p["stock"] < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para '{p['name']}'. Disponible: {p.get('stock', 0)}, solicitado: {item.quantity}",
                )

        subtotal = p["sale_price"] * item.quantity
        items_data.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "unit_price": p["sale_price"],
            "subtotal": subtotal,
            "product_type": p["type"],
        })
        added_total += subtotal

    # Insert new sale items and decrement stock
    for item_data in items_data:
        sale_item = {
            "sale_id": sale_id,
            "product_id": item_data["product_id"],
            "quantity": item_data["quantity"],
            "unit_price": item_data["unit_price"],
            "subtotal": item_data["subtotal"],
        }
        supabase.table("sale_items").insert(sale_item).execute()

        if item_data["product_type"] == "product":
            product = (
                supabase.table("products")
                .select("stock")
                .eq("id", item_data["product_id"])
                .single()
                .execute()
            )
            new_stock = product.data["stock"] - item_data["quantity"]
            if new_stock < 0:
                raise HTTPException(
                    status_code=400,
                    detail="Stock insuficiente (condición de carrera detectada)",
                )
            supabase.table("products").update({"stock": new_stock}).eq(
                "id", item_data["product_id"]
            ).execute()

    # Update sale total
    new_total = sale.data["total"] + added_total
    supabase.table("sales").update({"total": new_total}).eq("id", sale_id).execute()

    # Audit log
    supabase.table("audit_log").insert({
        "user_id": user["id"],
        "action": "fiado_add_items",
        "entity_type": "sale",
        "entity_id": sale_id,
        "old_values": {"total": sale.data["total"]},
        "new_values": {"total": new_total, "items_added": len(items_data)},
    }).execute()

    return get_sale_detail(sale_id)


def void_sale(sale_id: str, reason: str, user: dict) -> dict:
    """Void a sale and restore stock."""
    sale = (
        supabase.table("sales")
        .select("*")
        .eq("id", sale_id)
        .single()
        .execute()
    )
    if not sale.data:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    if sale.data["status"] == "voided":
        raise HTTPException(status_code=400, detail="La venta ya fue anulada")

    # Get sale items
    items = (
        supabase.table("sale_items")
        .select("*, products(type, stock)")
        .eq("sale_id", sale_id)
        .execute()
    )

    # Aggregate quantities per product (handles consolidated sales with
    # multiple sale_items rows for the same product)
    restore_map = {}
    for item in items.data:
        product_info = item.get("products")
        if product_info and product_info["type"] == "product":
            pid = item["product_id"]
            restore_map[pid] = restore_map.get(pid, 0) + item["quantity"]

    # Restore stock per product (read fresh stock to avoid stale join data)
    for pid, qty in restore_map.items():
        product = (
            supabase.table("products")
            .select("stock")
            .eq("id", pid)
            .single()
            .execute()
        )
        current_stock = product.data["stock"] or 0
        supabase.table("products").update({"stock": current_stock + qty}).eq(
            "id", pid
        ).execute()

    # Update sale status. Clear paid_payment_method and paid_at so a voided
    # sale never contributes to any cash closing aggregation.
    supabase.table("sales").update({
        "status": "voided",
        "voided_by": user["id"],
        "void_reason": reason,
        "voided_at": col_now().isoformat(),
        "paid_payment_method": None,
        "paid_at": None,
    }).eq("id", sale_id).execute()

    return get_sale_detail(sale_id)


def pay_sale(sale_id: str, data: PaySale, user: dict) -> dict:
    """Mark a pending fiado sale as completed and record how it was settled."""
    if data.payment_method not in VALID_PAY_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Método de pago inválido. Debe ser uno de: {', '.join(sorted(VALID_PAY_METHODS))}",
        )

    sale = (
        supabase.table("sales")
        .select("*")
        .eq("id", sale_id)
        .single()
        .execute()
    )
    if not sale.data:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    if sale.data["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden cobrar ventas pendientes (fiado)",
        )

    paid_at = col_now().isoformat()
    supabase.table("sales").update({
        "status": "completed",
        "paid_payment_method": data.payment_method,
        "paid_at": paid_at,
    }).eq("id", sale_id).execute()

    # Audit log — record both the status flip and the settlement method
    supabase.table("audit_log").insert({
        "user_id": user["id"],
        "action": "fiado_paid",
        "entity_type": "sale",
        "entity_id": sale_id,
        "old_values": {"status": "pending"},
        "new_values": {
            "status": "completed",
            "paid_payment_method": data.payment_method,
            "paid_at": paid_at,
        },
    }).execute()

    return get_sale_detail(sale_id)


def get_sale_detail(sale_id: str) -> dict:
    """Get sale with items and product names."""
    sale = (
        supabase.table("sales")
        .select("*, users!sales_user_id_fkey(full_name)")
        .eq("id", sale_id)
        .single()
        .execute()
    )
    if not sale.data:
        return None

    s = sale.data
    s["user_name"] = s.get("users", {}).get("full_name") if s.get("users") else None
    s.pop("users", None)

    items = (
        supabase.table("sale_items")
        .select("*, products(name)")
        .eq("sale_id", sale_id)
        .execute()
    )
    s["items"] = []
    for item in items.data:
        item["product_name"] = item.get("products", {}).get("name") if item.get("products") else None
        item.pop("products", None)
        s["items"].append(item)

    return s
