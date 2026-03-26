from fastapi import HTTPException
from app.database import supabase
from app.models.sale import SaleCreate


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

    # Restore stock for each product-type item
    for item in items.data:
        product_info = item.get("products")
        if product_info and product_info["type"] == "product":
            current_stock = product_info["stock"] or 0
            new_stock = current_stock + item["quantity"]
            supabase.table("products").update({"stock": new_stock}).eq(
                "id", item["product_id"]
            ).execute()

    # Update sale status
    from app.timezone import col_now

    supabase.table("sales").update({
        "status": "voided",
        "voided_by": user["id"],
        "void_reason": reason,
        "voided_at": col_now().isoformat(),
    }).eq("id", sale_id).execute()

    return get_sale_detail(sale_id)


def pay_sale(sale_id: str, user: dict) -> dict:
    """Mark a pending fiado sale as completed."""
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

    supabase.table("sales").update({"status": "completed"}).eq(
        "id", sale_id
    ).execute()

    # Audit log
    supabase.table("audit_log").insert({
        "user_id": user["id"],
        "action": "fiado_paid",
        "entity_type": "sale",
        "entity_id": sale_id,
        "old_values": {"status": "pending"},
        "new_values": {"status": "completed"},
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
