from pydantic import BaseModel
from typing import Optional


class StockAdjustmentCreate(BaseModel):
    product_id: str
    counted_quantity: int
    reason: Optional[str] = None


class StockAdjustmentResponse(BaseModel):
    id: str
    product_id: str
    counted_quantity: int
    system_quantity: int
    difference: int
    reason: Optional[str] = None
    adjusted_by: str
    adjusted_at: str
