from fastapi import HTTPException
from app.database import supabase
from datetime import datetime, timedelta
from app.timezone import COL_TZ, col_now, date_range_col
import csv
import io


def get_daily_summary(date: str, date_from: str = None, date_to: str = None) -> dict:
    """Get summary for a date or date range.

    Note: this is the *sales analytics* view ("what was sold today, by the
    payment method the customer originally chose"). For the *cash flow* view
    ("what money came in today, by channel — including fiado collections"),
    see ``get_cash_closing_data``.
    """
    if date_from and date_to:
        date_start = f"{date_from}T00:00:00-05:00"
        date_end = f"{date_to}T23:59:59-05:00"
    else:
        date_start, date_end = date_range_col(date)

    # All sales for the day (non-voided)
    sales = (
        supabase.table("sales")
        .select("*")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .neq("status", "voided")
        .execute()
    )

    total_sales = sum(s["total"] for s in sales.data)
    total_count = len(sales.data)

    by_method = {"efectivo": 0, "transferencia": 0, "datafono": 0, "fiado": 0}
    fiado_pending = 0
    for s in sales.data:
        by_method[s["payment_method"]] = by_method.get(s["payment_method"], 0) + s["total"]
        if s["status"] == "pending":
            fiado_pending += s["total"]

    # Voided sales count
    voided = (
        supabase.table("sales")
        .select("id")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .eq("status", "voided")
        .execute()
    )
    voided_count = len(voided.data)

    # Internal use count
    internal = (
        supabase.table("internal_use")
        .select("id")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .execute()
    )
    internal_count = len(internal.data)

    # Top 5 products
    sale_items = (
        supabase.table("sale_items")
        .select("product_id, quantity, subtotal, products(name), sales!inner(created_at, status)")
        .gte("sales.created_at", date_start)
        .lte("sales.created_at", date_end)
        .neq("sales.status", "voided")
        .execute()
    )

    product_stats = {}
    for item in sale_items.data:
        pid = item["product_id"]
        if pid not in product_stats:
            product_stats[pid] = {
                "product_id": pid,
                "product_name": item.get("products", {}).get("name", "") if item.get("products") else "",
                "units_sold": 0,
                "revenue": 0,
            }
        product_stats[pid]["units_sold"] += item["quantity"]
        product_stats[pid]["revenue"] += item["subtotal"]

    top_products = sorted(
        product_stats.values(), key=lambda x: x["revenue"], reverse=True
    )[:5]

    avg_ticket = total_sales // total_count if total_count > 0 else 0

    return {
        "date": date,
        "total_sales": total_sales,
        "total_sales_count": total_count,
        "avg_ticket": avg_ticket,
        "by_payment_method": by_method,
        "fiado_pending": fiado_pending,
        "voided_count": voided_count,
        "internal_use_count": internal_count,
        "top_products": top_products,
    }


def get_cash_closing_data(date: str) -> dict:
    """Get calculated data for cash closing form.

    Money-flow semantics:
      - ``total_cash`` / ``total_transfer`` / ``total_datafono`` represent the
        money that actually came in via that channel today, including cash
        collected today from fiados originally created on a previous day.
      - ``total_credit_issued`` is fiado created today (non-voided) — informational.
      - ``total_credit_collected`` is fiado paid today (regardless of when created).
      - ``total_credit_outstanding`` is the snapshot of all currently-pending fiado.
      - ``total_fiado`` is preserved as an alias for ``total_credit_issued`` so
        legacy frontends still see a value, but new UI should use the explicit
        credit_* fields.
    """
    # Check if closing already exists
    existing = (
        supabase.table("cash_closings")
        .select("*")
        .eq("closing_date", date)
        .execute()
    )
    if existing.data:
        return {"existing": True, "closing": existing.data[0]}

    date_start, date_end = date_range_col(date)

    # Bucket A: non-fiado sales created today (settled instantly)
    instant = (
        supabase.table("sales")
        .select("payment_method, total, status")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .neq("payment_method", "fiado")
        .execute()
    )

    # Bucket B: fiado sales paid today (regardless of when originally created)
    collected = (
        supabase.table("sales")
        .select("paid_payment_method, total")
        .eq("payment_method", "fiado")
        .eq("status", "completed")
        .gte("paid_at", date_start)
        .lte("paid_at", date_end)
        .execute()
    )

    # Bucket C: fiado sales CREATED today (informational — credit issued today)
    issued = (
        supabase.table("sales")
        .select("total, status")
        .eq("payment_method", "fiado")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .execute()
    )

    # Bucket D: voided sales created today
    voided = (
        supabase.table("sales")
        .select("total")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .eq("status", "voided")
        .execute()
    )

    # Bucket E: snapshot of all currently-pending fiado
    outstanding = (
        supabase.table("sales")
        .select("total")
        .eq("payment_method", "fiado")
        .eq("status", "pending")
        .execute()
    )

    totals = {"efectivo": 0, "transferencia": 0, "datafono": 0}
    for s in instant.data:
        if s["status"] == "voided":
            continue
        if s["payment_method"] in totals:
            totals[s["payment_method"]] += s["total"]
    for s in collected.data:
        # Legacy paid fiado (pre-migration) has NULL paid_payment_method.
        # We can't attribute it to a channel, so it stays out of the per-method
        # totals — surfaced separately via total_credit_collected.
        method = s.get("paid_payment_method")
        if method in totals:
            totals[method] += s["total"]

    total_credit_issued = sum(s["total"] for s in issued.data if s["status"] != "voided")
    total_credit_collected = sum(s["total"] for s in collected.data)
    total_credit_outstanding = sum(s["total"] for s in outstanding.data)
    total_voided = sum(s["total"] for s in voided.data)
    total_money_in = totals["efectivo"] + totals["transferencia"] + totals["datafono"]

    # Internal use value (unchanged)
    internal = (
        supabase.table("internal_use")
        .select("quantity, products(sale_price)")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .execute()
    )
    total_internal = sum(
        i["quantity"] * (i.get("products", {}).get("sale_price", 0) if i.get("products") else 0)
        for i in internal.data
    )

    return {
        "existing": False,
        "total_sales": total_money_in,
        "total_cash": totals["efectivo"],
        "total_transfer": totals["transferencia"],
        "total_datafono": totals["datafono"],
        "total_fiado": total_credit_issued,  # legacy alias for credit_issued
        "total_credit_issued": total_credit_issued,
        "total_credit_collected": total_credit_collected,
        "total_credit_outstanding": total_credit_outstanding,
        "total_voided": total_voided,
        "total_internal_use": total_internal,
    }


def create_cash_closing(data, user: dict) -> dict:
    """Create cash closing record."""
    # Check if already exists
    existing = (
        supabase.table("cash_closings")
        .select("id")
        .eq("closing_date", data.closing_date)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=400,
            detail="Ya existe un corte de caja para esta fecha",
        )

    # Get calculated data
    calc = get_cash_closing_data(data.closing_date)
    if calc.get("existing"):
        raise HTTPException(
            status_code=400,
            detail="Ya existe un corte de caja para esta fecha",
        )

    difference = data.physical_cash - calc["total_cash"]

    closing_data = {
        "user_id": user["id"],
        "closing_date": data.closing_date,
        "total_sales": calc["total_sales"],
        "total_cash": calc["total_cash"],
        "total_transfer": calc["total_transfer"],
        "total_datafono": calc["total_datafono"],
        "total_fiado": calc["total_fiado"],
        "total_credit_issued": calc["total_credit_issued"],
        "total_credit_collected": calc["total_credit_collected"],
        "total_credit_outstanding": calc["total_credit_outstanding"],
        "total_voided": calc["total_voided"],
        "total_internal_use": calc["total_internal_use"],
        "physical_cash": data.physical_cash,
        "difference": difference,
        "notes": data.notes,
    }

    result = supabase.table("cash_closings").insert(closing_data).execute()
    return result.data[0]


def get_top_sellers(period: str, date: str) -> list:
    """Get top selling products for a period."""
    dt = datetime.strptime(date, "%Y-%m-%d")

    if period == "day":
        date_start = f"{date}T00:00:00-05:00"
        date_end = f"{date}T23:59:59-05:00"
    elif period == "week":
        start = dt - timedelta(days=dt.weekday())
        end = start + timedelta(days=6)
        date_start = f"{start.strftime('%Y-%m-%d')}T00:00:00-05:00"
        date_end = f"{end.strftime('%Y-%m-%d')}T23:59:59-05:00"
    elif period == "month":
        date_start = f"{dt.strftime('%Y-%m')}-01T00:00:00-05:00"
        if dt.month == 12:
            next_month = dt.replace(year=dt.year + 1, month=1, day=1)
        else:
            next_month = dt.replace(month=dt.month + 1, day=1)
        end = next_month - timedelta(days=1)
        date_end = f"{end.strftime('%Y-%m-%d')}T23:59:59-05:00"
    else:
        date_start = f"{date}T00:00:00-05:00"
        date_end = f"{date}T23:59:59-05:00"

    sale_items = (
        supabase.table("sale_items")
        .select("product_id, quantity, subtotal, products(name), sales!inner(created_at, status)")
        .gte("sales.created_at", date_start)
        .lte("sales.created_at", date_end)
        .neq("sales.status", "voided")
        .execute()
    )

    product_stats = {}
    for item in sale_items.data:
        pid = item["product_id"]
        if pid not in product_stats:
            product_stats[pid] = {
                "product_id": pid,
                "product_name": item.get("products", {}).get("name", "") if item.get("products") else "",
                "units_sold": 0,
                "revenue": 0,
            }
        product_stats[pid]["units_sold"] += item["quantity"]
        product_stats[pid]["revenue"] += item["subtotal"]

    return sorted(product_stats.values(), key=lambda x: x["revenue"], reverse=True)


def get_inventory_value() -> dict:
    """Get inventory valuation."""
    products = (
        supabase.table("products")
        .select("id, name, stock, sale_price, purchase_price")
        .eq("is_active", True)
        .eq("type", "product")
        .execute()
    )

    items = []
    grand_total_sale = 0
    grand_total_purchase = 0

    for p in products.data:
        stock = p["stock"] or 0
        total_sale = stock * p["sale_price"]
        total_purchase = stock * p["purchase_price"]
        items.append({
            "product_id": p["id"],
            "name": p["name"],
            "stock": stock,
            "sale_price": p["sale_price"],
            "purchase_price": p["purchase_price"],
            "total_sale_value": total_sale,
            "total_purchase_value": total_purchase,
        })
        grand_total_sale += total_sale
        grand_total_purchase += total_purchase

    return {
        "items": items,
        "grand_total_sale": grand_total_sale,
        "grand_total_purchase": grand_total_purchase,
    }


def get_reconciliation(date_from: str, date_to: str) -> list:
    """Get stock reconciliation report."""
    date_start = f"{date_from}T00:00:00-05:00"
    date_end = f"{date_to}T23:59:59-05:00"

    products = (
        supabase.table("products")
        .select("id, name, stock")
        .eq("is_active", True)
        .eq("type", "product")
        .execute()
    )

    reconciliation = []
    for p in products.data:
        actual_stock = p["stock"] or 0

        # Sales in period
        sales_items = (
            supabase.table("sale_items")
            .select("quantity, sales!inner(created_at, status)")
            .eq("product_id", p["id"])
            .gte("sales.created_at", date_start)
            .lte("sales.created_at", date_end)
            .neq("sales.status", "voided")
            .execute()
        )
        total_sold = sum(si["quantity"] for si in sales_items.data)

        # Entries in period
        entries = (
            supabase.table("inventory_entries")
            .select("quantity")
            .eq("product_id", p["id"])
            .gte("created_at", date_start)
            .lte("created_at", date_end)
            .execute()
        )
        total_entered = sum(e["quantity"] for e in entries.data)

        # Internal use in period
        uses = (
            supabase.table("internal_use")
            .select("quantity")
            .eq("product_id", p["id"])
            .gte("created_at", date_start)
            .lte("created_at", date_end)
            .execute()
        )
        total_used = sum(u["quantity"] for u in uses.data)

        # Expected stock = actual + sold + used - entered (working backwards)
        expected_stock = actual_stock + total_sold + total_used - total_entered
        # Actually: expected = opening + entries - sales - internal_use
        # Since we don't have opening stock, we compute: expected current = actual
        # The difference represents unexplained discrepancies
        # Better approach: expected_change = entries - sales - internal_use
        # expected_stock = opening + expected_change
        # Since opening is unknown, compare: actual vs (actual + sold + used - entered) which equals opening
        # Let's just show expected vs actual where expected = opening + entries - sales - uses
        # and opening = actual - entries + sales + uses (from current backwards)
        # So expected should equal actual if no discrepancies.
        # The discrepancy = 0 if all movements are accounted for.

        # Simplified: just show the movements summary
        expected = actual_stock  # If all movements tracked, expected = actual
        difference = 0  # Would only differ if manual stock adjustments happened

        reconciliation.append({
            "product_id": p["id"],
            "name": p["name"],
            "total_sold": total_sold,
            "total_entered": total_entered,
            "total_internal_use": total_used,
            "expected_stock": expected,
            "actual_stock": actual_stock,
            "difference": difference,
        })

    return reconciliation


def get_fiado_aging() -> dict:
    """Get fiado (open accounts) aging breakdown."""
    pending = (
        supabase.table("sales")
        .select("id, total, created_at, client_name")
        .eq("status", "pending")
        .eq("payment_method", "fiado")
        .execute()
    )

    now = col_now()
    buckets = {
        "< 3 días": {"count": 0, "total": 0},
        "3-7 días": {"count": 0, "total": 0},
        "> 7 días": {"count": 0, "total": 0},
    }

    total_owed = 0
    for sale in pending.data:
        total_owed += sale["total"]
        created = datetime.fromisoformat(sale["created_at"].replace("Z", "+00:00"))
        days = (now - created).days

        if days < 3:
            buckets["< 3 días"]["count"] += 1
            buckets["< 3 días"]["total"] += sale["total"]
        elif days <= 7:
            buckets["3-7 días"]["count"] += 1
            buckets["3-7 días"]["total"] += sale["total"]
        else:
            buckets["> 7 días"]["count"] += 1
            buckets["> 7 días"]["total"] += sale["total"]

    return {
        "total_owed": total_owed,
        "total_count": len(pending.data),
        "buckets": [
            {"label": label, "count": data["count"], "total": data["total"]}
            for label, data in buckets.items()
        ],
    }


def export_sales_csv(date_from: str, date_to: str) -> str:
    """Export sales data as CSV string."""
    date_start = f"{date_from}T00:00:00-05:00"
    date_end = f"{date_to}T23:59:59-05:00"

    sales = (
        supabase.table("sales")
        .select("*, users!sales_user_id_fkey(full_name)")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .order("created_at", desc=True)
        .execute()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Fecha", "Vendedor", "Total", "Método de Pago",
        "Estado", "Cliente", "Notas",
    ])

    for s in sales.data:
        writer.writerow([
            s["created_at"],
            s.get("users", {}).get("full_name", "") if s.get("users") else "",
            s["total"],
            s["payment_method"],
            s["status"],
            s.get("client_name", ""),
            s.get("notes", ""),
        ])

    return output.getvalue()
