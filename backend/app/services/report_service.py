from fastapi import HTTPException
from app.database import supabase
from datetime import datetime, timedelta
from app.timezone import COL_TZ, col_now, date_range_col
import csv
import io


def get_daily_summary(date: str, date_from: str = None, date_to: str = None) -> dict:
    """Get summary for a date or date range (money-flow view).

    Semantics:
      - ``total_sales`` — accrual: sum of non-voided sales CREATED in range.
      - ``by_payment_method.{efectivo,transferencia,datafono}`` — cash flow:
        money actually received via that channel during the range (from
        ``sale_payments.paid_at``). Includes fiado settlements that happened
        in the range and auto-splits mixto sales.
      - ``by_payment_method.fiado`` — "por cobrar": sum of fiado sales
        created in range that are still pending now (same as ``fiado_pending``).
      - ``fiado_pending`` — pending fiado created in range.
      - ``fiado_settled_in_range`` — fiado sales whose ``paid_at`` lies in
        range (transparency KPI).

    Note: ``total_sales`` (accrual) and ``sum(by_payment_method)`` (cash flow)
    need not match exactly — a fiado created on day D and paid on D+5 appears
    in ``total_sales`` on D and in the ``efectivo`` bucket on D+5.
    """
    if date_from and date_to:
        date_start = f"{date_from}T00:00:00-05:00"
        date_end = f"{date_to}T23:59:59-05:00"
    else:
        date_start, date_end = date_range_col(date)

    # Sales created in range (non-voided) — used for total_sales, fiado_pending
    sales = (
        supabase.table("sales")
        .select("id, total, status, payment_method")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .neq("status", "voided")
        .execute()
    )

    total_sales = sum(s["total"] for s in sales.data)
    total_count = len(sales.data)

    # Pending fiado created in range (= por cobrar from these sales)
    fiado_pending = sum(
        s["total"] for s in sales.data
        if s["payment_method"] == "fiado" and s["status"] == "pending"
    )

    # Money actually received via each channel in range (cash-flow view),
    # sourced from sale_payments. This captures non-fiado sales (where
    # paid_at ≈ created_at), mixto splits, and fiado settlements in range.
    payments_in_range = (
        supabase.table("sale_payments")
        .select("payment_method, amount, sales!inner(status)")
        .gte("paid_at", date_start)
        .lte("paid_at", date_end)
        .neq("sales.status", "voided")
        .execute()
    )
    by_method = {"efectivo": 0, "transferencia": 0, "datafono": 0, "fiado": 0}
    for p in payments_in_range.data:
        if p["payment_method"] in by_method:
            by_method[p["payment_method"]] += p["amount"]
    # Fiado bucket in the money-flow view is the pending balance (por cobrar)
    by_method["fiado"] = fiado_pending

    # Credit collected in range (fiado sales whose paid_at lies in range)
    settled = (
        supabase.table("sales")
        .select("total")
        .eq("payment_method", "fiado")
        .eq("status", "completed")
        .gte("paid_at", date_start)
        .lte("paid_at", date_end)
        .execute()
    )
    fiado_settled_in_range = sum(s["total"] for s in settled.data)

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
        "fiado_settled_in_range": fiado_settled_in_range,
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

    # Money received today, per channel — single source of truth is now the
    # sale_payments table, joined to sales to filter out voided sales.
    payments_today = (
        supabase.table("sale_payments")
        .select("payment_method, amount, sales!inner(status)")
        .gte("paid_at", date_start)
        .lte("paid_at", date_end)
        .neq("sales.status", "voided")
        .execute()
    )

    totals = {"efectivo": 0, "transferencia": 0, "datafono": 0}
    for p in payments_today.data:
        if p["payment_method"] in totals:
            totals[p["payment_method"]] += p["amount"]

    # Credit collected today: every fiado sale settled today contributes its
    # full total exactly once, regardless of how it was paid (single method,
    # split, or legacy NULL paid_payment_method).
    collected = (
        supabase.table("sales")
        .select("total")
        .eq("payment_method", "fiado")
        .eq("status", "completed")
        .gte("paid_at", date_start)
        .lte("paid_at", date_end)
        .execute()
    )
    total_credit_collected = sum(s["total"] for s in collected.data)

    # Credit issued today: fiado sales CREATED today (regardless of paid status)
    issued = (
        supabase.table("sales")
        .select("total, status")
        .eq("payment_method", "fiado")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .execute()
    )

    # Voided sales created today
    voided = (
        supabase.table("sales")
        .select("total")
        .gte("created_at", date_start)
        .lte("created_at", date_end)
        .eq("status", "voided")
        .execute()
    )

    # Historical snapshot of fiado outstanding at the END of the selected day.
    # Fetch all fiado sales created on or before date_end and filter in Python
    # to include only those that were still pending + non-voided by cutoff.
    fiado_sales = (
        supabase.table("sales")
        .select("total, status, created_at, paid_at, voided_at")
        .eq("payment_method", "fiado")
        .lte("created_at", date_end)
        .execute()
    )
    cutoff = date_end
    total_credit_outstanding = sum(
        s["total"] for s in fiado_sales.data
        if (s.get("paid_at") is None or s["paid_at"] > cutoff)
        and not (s["status"] == "voided" and (s.get("voided_at") or "") <= cutoff)
    )

    total_credit_issued = sum(s["total"] for s in issued.data if s["status"] != "voided")
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


def get_daily_breakdown(date_from: str, date_to: str) -> list:
    """Return a per-date breakdown over ``[date_from, date_to]``.

    Each row: ``{date, total_sales, sales_count, by_payment_method,
    fiado_pending, fiado_settled_in_range}`` — same semantics as
    ``get_daily_summary`` for a single day. Includes zero rows for days
    with no activity so the table is dense.
    """
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    if end < start:
        raise HTTPException(
            status_code=400,
            detail="date_to debe ser mayor o igual a date_from",
        )
    # Cap the span to avoid runaway loops; months of data is the expected use.
    span_days = (end - start).days
    if span_days > 366:
        raise HTTPException(
            status_code=400,
            detail="El rango no puede superar 366 días",
        )

    rows = []
    current = start
    while current <= end:
        day_str = current.strftime("%Y-%m-%d")
        summary = get_daily_summary(day_str)
        rows.append({
            "date": day_str,
            "total_sales": summary["total_sales"],
            "sales_count": summary["total_sales_count"],
            "by_payment_method": summary["by_payment_method"],
            "fiado_pending": summary["fiado_pending"],
            "fiado_settled_in_range": summary["fiado_settled_in_range"],
        })
        current += timedelta(days=1)
    return rows


def get_top_sellers(
    period: str,
    date: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list:
    """Get top selling products for a period or explicit range.

    When ``date_from`` and ``date_to`` are both provided they override the
    ``period`` computation — used by the "Rango" tab in the frontend.
    """
    if date_from and date_to:
        date_start = f"{date_from}T00:00:00-05:00"
        date_end = f"{date_to}T23:59:59-05:00"
    else:
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
    """Per-product movement summary over a date range.

    Columns:
      - total_sold / total_entered / total_internal_use — movements in range
      - total_adjustments — sum of ``stock_adjustments.difference`` in range
        (positive = found stock; negative = shrinkage)
      - actual_stock — current value of products.stock
      - expected_stock — what stock would be if no manual adjustments were
        recorded (``actual_stock - total_adjustments``)
      - difference — equals ``total_adjustments`` so the column reads "how
        much of the current stock is unexplained by movements alone". Zero
        when no physical counts were entered in the range.
    """
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

        # Stock adjustments in period
        adjustments = (
            supabase.table("stock_adjustments")
            .select("difference")
            .eq("product_id", p["id"])
            .gte("adjusted_at", date_start)
            .lte("adjusted_at", date_end)
            .execute()
        )
        total_adjustments = sum(a["difference"] for a in adjustments.data)

        expected_stock = actual_stock - total_adjustments
        difference = total_adjustments

        reconciliation.append({
            "product_id": p["id"],
            "name": p["name"],
            "total_sold": total_sold,
            "total_entered": total_entered,
            "total_internal_use": total_used,
            "total_adjustments": total_adjustments,
            "expected_stock": expected_stock,
            "actual_stock": actual_stock,
            "difference": difference,
        })

    return reconciliation


def get_fiado_aging(as_of: str | None = None) -> dict:
    """Fiado (por cobrar) aging breakdown.

    When ``as_of`` is provided, the buckets reflect the state at the end of
    that date — i.e., fiados outstanding at that cutoff, aged from that
    cutoff. When omitted, uses the current moment (live snapshot).
    """
    if as_of:
        cutoff = datetime.strptime(as_of, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=COL_TZ
        )
    else:
        cutoff = col_now()

    cutoff_iso = cutoff.isoformat()

    fiado_sales = (
        supabase.table("sales")
        .select("id, total, created_at, client_name, status, paid_at, voided_at")
        .eq("payment_method", "fiado")
        .lte("created_at", cutoff_iso)
        .execute()
    )

    buckets = {
        "< 3 días": {"count": 0, "total": 0},
        "3-7 días": {"count": 0, "total": 0},
        "> 7 días": {"count": 0, "total": 0},
    }

    total_owed = 0
    for sale in fiado_sales.data:
        # Skip if already settled at cutoff
        if sale.get("paid_at") and sale["paid_at"] <= cutoff_iso:
            continue
        # Skip if voided at cutoff
        if sale["status"] == "voided" and (sale.get("voided_at") or "") <= cutoff_iso:
            continue

        total_owed += sale["total"]
        created = datetime.fromisoformat(sale["created_at"].replace("Z", "+00:00"))
        days = (cutoff - created).days

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
        "total_count": sum(b["count"] for b in buckets.values()),
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

    # Batch-fetch payment splits for any mixto sales in the result set so
    # we can expand them into the Detalle de Pago column.
    sale_ids = [s["id"] for s in sales.data]
    payments_by_sale: dict = {}
    if sale_ids:
        splits = (
            supabase.table("sale_payments")
            .select("sale_id, payment_method, amount")
            .in_("sale_id", sale_ids)
            .execute()
        )
        for sp in splits.data:
            payments_by_sale.setdefault(sp["sale_id"], []).append(sp)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Fecha", "Vendedor", "Total", "Método de Pago", "Detalle de Pago",
        "Estado", "Cliente", "Notas",
    ])

    for s in sales.data:
        detail = ""
        if s["payment_method"] == "mixto":
            detail = "; ".join(
                f"{p['payment_method']}:{p['amount']}"
                for p in payments_by_sale.get(s["id"], [])
            )
        writer.writerow([
            s["created_at"],
            s.get("users", {}).get("full_name", "") if s.get("users") else "",
            s["total"],
            s["payment_method"],
            detail,
            s["status"],
            s.get("client_name", ""),
            s.get("notes", ""),
        ])

    return output.getvalue()
