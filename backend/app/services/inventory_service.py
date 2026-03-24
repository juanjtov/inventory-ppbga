from fastapi import HTTPException
from app.database import supabase
from app.models.inventory import InventoryEntryCreate, InternalUseCreate


def create_entry(data: InventoryEntryCreate, user: dict) -> dict:
    """Create inventory entry (restock) and increment product stock."""
    # Get current product
    product = (
        supabase.table("products")
        .select("*")
        .eq("id", data.product_id)
        .single()
        .execute()
    )
    if not product.data:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    p = product.data
    expected_price = p["purchase_price"]
    actual_price = data.actual_price if not data.price_confirmed else expected_price

    # Insert inventory entry
    entry_data = {
        "product_id": data.product_id,
        "user_id": user["id"],
        "quantity": data.quantity,
        "supplier_id": data.supplier_id,
        "expected_price": expected_price,
        "actual_price": actual_price,
        "price_confirmed": data.price_confirmed,
    }
    result = supabase.table("inventory_entries").insert(entry_data).execute()

    # If price not confirmed, update product's purchase_price and log audit
    if not data.price_confirmed and data.actual_price is not None:
        supabase.table("products").update(
            {"purchase_price": data.actual_price}
        ).eq("id", data.product_id).execute()

        # Audit log
        supabase.table("audit_log").insert({
            "user_id": user["id"],
            "action": "purchase_price_change",
            "entity_type": "product",
            "entity_id": data.product_id,
            "old_values": {"purchase_price": expected_price},
            "new_values": {"purchase_price": data.actual_price},
        }).execute()

    # Increment stock
    current_stock = p["stock"] if p["stock"] is not None else 0
    new_stock = current_stock + data.quantity
    supabase.table("products").update({"stock": new_stock}).eq(
        "id", data.product_id
    ).execute()

    return result.data[0]


def create_internal_use(data: InternalUseCreate, user: dict) -> dict:
    """Create internal use record and decrement stock."""
    # Get current product
    product = (
        supabase.table("products")
        .select("*")
        .eq("id", data.product_id)
        .single()
        .execute()
    )
    if not product.data:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    p = product.data

    if p["type"] == "service":
        raise HTTPException(
            status_code=400, detail="No se puede registrar uso interno de un servicio"
        )

    if p["stock"] is None or p["stock"] < data.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente. Disponible: {p.get('stock', 0)}, solicitado: {data.quantity}",
        )

    if len(data.reason.strip()) < 5:
        raise HTTPException(
            status_code=400, detail="La razón debe tener al menos 5 caracteres"
        )

    # Insert internal use
    use_data = {
        "product_id": data.product_id,
        "user_id": user["id"],
        "quantity": data.quantity,
        "reason": data.reason,
    }
    result = supabase.table("internal_use").insert(use_data).execute()

    # Decrement stock
    new_stock = p["stock"] - data.quantity
    supabase.table("products").update({"stock": new_stock}).eq(
        "id", data.product_id
    ).execute()

    return result.data[0]


def get_movements(product_id: str) -> list:
    """Get unified timeline of movements for a product."""
    movements = []

    # Sales involving this product
    sale_items = (
        supabase.table("sale_items")
        .select("*, sales(id, created_at, payment_method, status, voided_at, user_id, users!sales_user_id_fkey(full_name))")
        .eq("product_id", product_id)
        .execute()
    )
    for si in sale_items.data:
        sale = si.get("sales", {})
        if not sale:
            continue
        user_name = sale.get("users", {}).get("full_name", "") if sale.get("users") else ""

        movements.append({
            "id": si["id"],
            "type": "sale",
            "quantity": si["quantity"],
            "date": sale.get("created_at", ""),
            "details": {
                "sale_id": sale.get("id"),
                "unit_price": si["unit_price"],
                "subtotal": si["subtotal"],
                "payment_method": sale.get("payment_method"),
                "status": sale.get("status"),
                "user_name": user_name,
            },
        })

        # If voided, add a void entry
        if sale.get("status") == "voided" and sale.get("voided_at"):
            movements.append({
                "id": f"{si['id']}-void",
                "type": "void",
                "quantity": si["quantity"],
                "date": sale.get("voided_at", ""),
                "details": {
                    "sale_id": sale.get("id"),
                    "user_name": user_name,
                },
            })

    # Inventory entries
    entries = (
        supabase.table("inventory_entries")
        .select("*, suppliers(name), users(full_name)")
        .eq("product_id", product_id)
        .execute()
    )
    for e in entries.data:
        movements.append({
            "id": e["id"],
            "type": "entry",
            "quantity": e["quantity"],
            "date": e["created_at"],
            "details": {
                "supplier_name": e.get("suppliers", {}).get("name") if e.get("suppliers") else None,
                "expected_price": e["expected_price"],
                "actual_price": e["actual_price"],
                "price_confirmed": e["price_confirmed"],
                "user_name": e.get("users", {}).get("full_name") if e.get("users") else None,
            },
        })

    # Internal use
    uses = (
        supabase.table("internal_use")
        .select("*, users(full_name)")
        .eq("product_id", product_id)
        .execute()
    )
    for u in uses.data:
        movements.append({
            "id": u["id"],
            "type": "internal_use",
            "quantity": u["quantity"],
            "date": u["created_at"],
            "details": {
                "reason": u["reason"],
                "user_name": u.get("users", {}).get("full_name") if u.get("users") else None,
            },
        })

    # Sort by date descending
    movements.sort(key=lambda m: m["date"], reverse=True)
    return movements
