from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import require_role
from app.models.stock_adjustment import StockAdjustmentCreate
from app.services.stock_adjustment_service import create_adjustment, list_adjustments

router = APIRouter()


@router.post("")
async def create_adjustment_endpoint(
    data: StockAdjustmentCreate,
    user=Depends(require_role("owner")),
):
    return create_adjustment(data, user)


@router.get("")
async def list_adjustments_endpoint(
    product_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(default=100, ge=1, le=1000),
    user=Depends(require_role("owner")),
):
    return list_adjustments(
        product_id=product_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
