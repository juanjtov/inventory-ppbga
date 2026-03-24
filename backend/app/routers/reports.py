from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.auth import get_current_user, require_role
from app.models.cash_closing import CashClosingCreate
from app.services.report_service import (
    get_daily_summary,
    get_cash_closing_data,
    create_cash_closing,
    get_top_sellers,
    get_inventory_value,
    get_reconciliation,
    get_fiado_aging,
    export_sales_csv,
)

router = APIRouter()


@router.get("/daily-summary")
async def daily_summary(
    date: str = Query(..., description="Fecha en formato YYYY-MM-DD"),
    date_from: Optional[str] = Query(None, description="Fecha inicio rango"),
    date_to: Optional[str] = Query(None, description="Fecha fin rango"),
    user=Depends(require_role("owner")),
):
    try:
        data = get_daily_summary(date, date_from=date_from, date_to=date_to)
    except Exception:
        raise HTTPException(
            status_code=500, detail="Error al obtener el resumen diario"
        )
    return data


@router.get("/cash-closing")
async def cash_closing_get(
    date: str = Query(..., description="Fecha en formato YYYY-MM-DD"),
    user=Depends(require_role("owner", "admin")),
):
    try:
        data = get_cash_closing_data(date)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al obtener los datos de cierre de caja",
        )
    return data


@router.post("/cash-closing")
async def cash_closing_create(
    data: CashClosingCreate,
    user=Depends(require_role("owner", "admin")),
):
    try:
        result = create_cash_closing(data, user)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500, detail="Error al crear el cierre de caja"
        )
    return result


@router.get("/top-sellers")
async def top_sellers(
    period: str = Query(
        ..., description="Periodo: day, week o month"
    ),
    date: str = Query(..., description="Fecha en formato YYYY-MM-DD"),
    user=Depends(require_role("owner")),
):
    if period not in ("day", "week", "month"):
        raise HTTPException(
            status_code=400,
            detail="Periodo no válido. Use: day, week o month",
        )
    try:
        data = get_top_sellers(period, date)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al obtener los productos más vendidos",
        )
    return data


@router.get("/inventory-value")
async def inventory_value(
    user=Depends(require_role("owner")),
):
    try:
        data = get_inventory_value()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al obtener el valor del inventario",
        )
    return data


@router.get("/reconciliation")
async def reconciliation(
    date_from: str = Query(
        ..., description="Fecha inicial en formato YYYY-MM-DD"
    ),
    date_to: str = Query(
        ..., description="Fecha final en formato YYYY-MM-DD"
    ),
    user=Depends(require_role("owner")),
):
    try:
        data = get_reconciliation(date_from, date_to)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al obtener la conciliación",
        )
    return data


@router.get("/fiado-aging")
async def fiado_aging(
    user=Depends(require_role("owner")),
):
    try:
        data = get_fiado_aging()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al obtener el reporte de fiados pendientes",
        )
    return data


@router.get("/export/sales")
async def export_sales(
    date_from: str = Query(
        ..., description="Fecha inicial en formato YYYY-MM-DD"
    ),
    date_to: str = Query(
        ..., description="Fecha final en formato YYYY-MM-DD"
    ),
    user=Depends(require_role("owner")),
):
    try:
        csv_content = export_sales_csv(date_from, date_to)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al exportar las ventas",
        )

    filename = f"ventas_{date_from}_{date_to}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
