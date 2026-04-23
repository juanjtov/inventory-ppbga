from fastapi import HTTPException
from app.database import supabase
from app.models.sale import SaleCreate, AddItemsRequest, PaySale
from app.timezone import col_now, date_range_col


VALID_PAY_METHODS = {"efectivo", "datafono", "transferencia"}


def _atomic_decrement(product_id: str, qty: int) -> int:
    """Atomically decrement product stock. Raises HTTPException(400) if
    stock would go negative or the product is not stock-tracked."""
    try:
        res = supabase.rpc(
            "decrement_stock",
            {"p_product_id": product_id, "p_qty": qty},
        ).execute()
    except Exception as e:
        msg = str(e).lower()
        if "insufficient_stock" in msg:
            raise HTTPException(
                status_code=400, detail="Stock insuficiente"
            )
        raise HTTPException(status_code=500, detail="Error actualizando stock")
    return res.data


def _atomic_increment(product_id: str, qty: int) -> int:
    """Atomically increment product stock (restock path). Raises 500 on error."""
    try:
        res = supabase.rpc(
            "increment_stock",
            {"p_product_id": product_id, "p_qty": qty},
        ).execute()
    except Exception:
        raise HTTPException(status_code=500, detail="Error actualizando stock")
    return res.data


def _validate_split(payments, expected_total: int):
    """Validate a split-payment list. Raises HTTPException(400) on any issue.

    Rules:
    - At least 2 entries.
    - Each method must be in VALID_PAY_METHODS (no fiado, no mixto).
    - No method may appear twice (uniqueness keeps reconciliation simple).
    - Each amount must be > 0.
    - The sum of amounts must equal expected_total exactly.
    """
    if not payments or len(payments) < 2:
        raise HTTPException(
            status_code=400,
            detail="Un pago dividido debe tener al menos 2 métodos",
        )
    seen = set()
    total = 0
    for p in payments:
        if p.payment_method not in VALID_PAY_METHODS:
            raise HTTPException(
                status_code=400,
                detail=f"Método inválido en split: {p.payment_method}",
            )
        if p.payment_method in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Método duplicado en split: {p.payment_method}",
            )
        if p.amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Cada monto del split debe ser mayor a 0",
            )
        seen.add(p.payment_method)
        total += p.amount
    if total != expected_total:
        raise HTTPException(
            status_code=400,
            detail=f"La suma del split ({total}) no coincide con el total ({expected_total})",
        )


def _insert_sale_payments(sale_id: str, entries, paid_at: str, user_id: str):
    """Insert one or more sale_payments rows. ``entries`` is a list of
    (payment_method, amount) tuples."""
    rows = [
        {
            "sale_id": sale_id,
            "payment_method": method,
            "amount": amount,
            "paid_at": paid_at,
            "created_by": user_id,
        }
        for method, amount in entries
    ]
    if rows:
        supabase.table("sale_payments").insert(rows).execute()


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

    # Validate split payments if mixto
    if data.payment_method == "mixto":
        _validate_split(data.payments, total)

    # Determine status — only fiado is pending; mixto is settled instantly
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

    # Insert sale items and atomically decrement stock
    for item_data in items_data:
        sale_item = {
            "sale_id": sale["id"],
            "product_id": item_data["product_id"],
            "quantity": item_data["quantity"],
            "unit_price": item_data["unit_price"],
            "subtotal": item_data["subtotal"],
        }
        supabase.table("sale_items").insert(sale_item).execute()

        if item_data["product_type"] == "product":
            _atomic_decrement(item_data["product_id"], item_data["quantity"])

    # Record sale_payments rows for any settled-instantly sale.
    # Fiado has no money to attribute yet — that happens in pay_sale().
    if data.payment_method != "fiado":
        paid_at = col_now().isoformat()
        if data.payment_method == "mixto":
            entries = [(p.payment_method, p.amount) for p in data.payments]
        else:
            entries = [(data.payment_method, total)]
        _insert_sale_payments(sale["id"], entries, paid_at, user["id"])

    # Audit log
    supabase.table("audit_log").insert({
        "user_id": user["id"],
        "action": "sale_created",
        "entity_type": "sale",
        "entity_id": sale["id"],
        "old_values": None,
        "new_values": {
            "total": total,
            "payment_method": data.payment_method,
            "status": status,
            "client_name": data.client_name,
            "item_count": len(items_data),
        },
    }).execute()

    # Fetch complete sale with items
    return get_sale_detail(sale["id"])


def get_sales_summary(
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    payment_method: str | None = None,
) -> dict:
    """Range-wide sales totals — independent of list pagination.

    Returns the four cards shown on Historial de Ventas:
      - total_count: count of sales matching the filters
      - total_amount: sum of sale.total where status != 'voided'
      - voided_count: count where status == 'voided'
      - fiado_pending: sum of sale.total where status='pending' AND
        payment_method='fiado' (matches the "por cobrar" KPI)
    """
    query = supabase.table("sales").select("total, status, payment_method")
    if date_from:
        query = query.gte("created_at", f"{date_from}T00:00:00-05:00")
    if date_to:
        query = query.lte("created_at", f"{date_to}T23:59:59-05:00")
    if status:
        query = query.eq("status", status)
    if payment_method:
        query = query.eq("payment_method", payment_method)
    result = query.execute()

    total_count = len(result.data)
    total_amount = sum(s["total"] for s in result.data if s["status"] != "voided")
    voided_count = sum(1 for s in result.data if s["status"] == "voided")
    fiado_pending = sum(
        s["total"] for s in result.data
        if s["status"] == "pending" and s["payment_method"] == "fiado"
    )
    return {
        "total_count": total_count,
        "total_amount": total_amount,
        "voided_count": voided_count,
        "fiado_pending": fiado_pending,
    }


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

    # Insert new sale items and atomically decrement stock
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
            _atomic_decrement(item_data["product_id"], item_data["quantity"])

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


def remove_item_from_sale(sale_id: str, item_id: str, user: dict) -> dict:
    """Remove a single line item from a pending fiado sale and restock the product.

    If the last item is removed, the sale is auto-voided so it disappears from
    Cuentas Abiertas instead of lingering as an empty open account.
    """
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
            detail="Solo se pueden eliminar items de ventas pendientes",
        )

    if sale.data["payment_method"] != "fiado":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden eliminar items de cuentas por cobrar",
        )

    # Fetch the sale_item and verify it belongs to this sale
    try:
        item = (
            supabase.table("sale_items")
            .select("*, products(type)")
            .eq("id", item_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Item no encontrado en esta venta")

    if not item.data or item.data["sale_id"] != sale_id:
        raise HTTPException(status_code=404, detail="Item no encontrado en esta venta")

    item_data = item.data
    product_info = item_data.get("products") or {}
    is_product = product_info.get("type") == "product"

    # Restock product (services don't track stock) — atomic
    if is_product:
        _atomic_increment(item_data["product_id"], item_data["quantity"])

    # Delete the sale_item
    supabase.table("sale_items").delete().eq("id", item_id).execute()

    # Compute new total
    new_total = sale.data["total"] - item_data["subtotal"]

    # Audit log
    supabase.table("audit_log").insert({
        "user_id": user["id"],
        "action": "fiado_remove_item",
        "entity_type": "sale",
        "entity_id": sale_id,
        "old_values": {
            "total": sale.data["total"],
            "removed_item": {
                "product_id": item_data["product_id"],
                "quantity": item_data["quantity"],
                "subtotal": item_data["subtotal"],
            },
        },
        "new_values": {"total": new_total},
    }).execute()

    # If the sale is now empty, auto-void it (cleaner than leaving an empty fiado)
    remaining = (
        supabase.table("sale_items")
        .select("id")
        .eq("sale_id", sale_id)
        .execute()
    )
    if not remaining.data:
        supabase.table("sales").update({
            "status": "voided",
            "voided_by": user["id"],
            "void_reason": "Auto-anulada: todos los items eliminados",
            "voided_at": col_now().isoformat(),
            "total": 0,
        }).eq("id", sale_id).execute()
    else:
        supabase.table("sales").update({"total": new_total}).eq("id", sale_id).execute()

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

    # Restore stock per product — atomic
    for pid, qty in restore_map.items():
        _atomic_increment(pid, qty)

    # Update sale status. Clear paid_payment_method and paid_at so a voided
    # sale never contributes to any cash closing aggregation.
    # Note: we deliberately do NOT delete sale_payments rows. The cash
    # closing query joins on sales.status != 'voided' so voided rows are
    # filtered out, preserving the audit trail (mirrors how sale_items are
    # kept on void).
    old_status = sale.data["status"]
    supabase.table("sales").update({
        "status": "voided",
        "voided_by": user["id"],
        "void_reason": reason,
        "voided_at": col_now().isoformat(),
        "paid_payment_method": None,
        "paid_at": None,
    }).eq("id", sale_id).execute()

    # Audit log
    supabase.table("audit_log").insert({
        "user_id": user["id"],
        "action": "sale_voided",
        "entity_type": "sale",
        "entity_id": sale_id,
        "old_values": {"status": old_status},
        "new_values": {"status": "voided", "reason": reason},
    }).execute()

    return get_sale_detail(sale_id)


def pay_sale(sale_id: str, data: PaySale, user: dict) -> dict:
    """Mark a pending fiado sale as completed and record how it was settled.

    Accepts either a single ``payment_method`` (legacy single-channel
    settlement) or a ``payments`` list (split settlement). Exactly one of
    the two must be provided.
    """
    has_single = data.payment_method is not None
    has_split = data.payments is not None and len(data.payments) > 0

    if has_single and has_split:
        raise HTTPException(
            status_code=400,
            detail="Provee solo payment_method o payments, no ambos",
        )
    if not has_single and not has_split:
        raise HTTPException(
            status_code=400,
            detail="Debes proveer payment_method o payments",
        )

    if has_single and data.payment_method not in VALID_PAY_METHODS:
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

    if has_split:
        _validate_split(data.payments, sale.data["total"])

    paid_at = col_now().isoformat()

    if has_single:
        # Single-method settlement keeps paid_payment_method populated
        # (backwards compatible with migration 002 reporting)
        sale_update = {
            "status": "completed",
            "paid_payment_method": data.payment_method,
            "paid_at": paid_at,
        }
        entries = [(data.payment_method, sale.data["total"])]
        audit_new_values = {
            "status": "completed",
            "paid_payment_method": data.payment_method,
            "paid_at": paid_at,
        }
    else:
        # Split settlement: leave paid_payment_method NULL — the per-channel
        # attribution lives in sale_payments rows.
        sale_update = {
            "status": "completed",
            "paid_payment_method": None,
            "paid_at": paid_at,
        }
        entries = [(p.payment_method, p.amount) for p in data.payments]
        audit_new_values = {
            "status": "completed",
            "paid_at": paid_at,
            "payments": [
                {"payment_method": p.payment_method, "amount": p.amount}
                for p in data.payments
            ],
        }

    supabase.table("sales").update(sale_update).eq("id", sale_id).execute()
    _insert_sale_payments(sale_id, entries, paid_at, user["id"])

    # Audit log — record both the status flip and the settlement attribution
    supabase.table("audit_log").insert({
        "user_id": user["id"],
        "action": "fiado_paid",
        "entity_type": "sale",
        "entity_id": sale_id,
        "old_values": {"status": "pending"},
        "new_values": audit_new_values,
    }).execute()

    return get_sale_detail(sale_id)


def get_sale_detail(sale_id: str) -> dict:
    """Get sale with items, payments, and product names."""
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

    payments = (
        supabase.table("sale_payments")
        .select("id, payment_method, amount, paid_at")
        .eq("sale_id", sale_id)
        .order("created_at")
        .execute()
    )
    s["payments"] = payments.data or []

    return s
