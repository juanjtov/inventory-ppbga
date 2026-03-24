from pydantic import BaseModel
from typing import Optional


class CashClosingCreate(BaseModel):
    closing_date: str  # YYYY-MM-DD
    physical_cash: int
    notes: Optional[str] = None


class CashClosingResponse(BaseModel):
    id: str
    user_id: str
    closing_date: str
    total_sales: int
    total_cash: int
    total_transfer: int
    total_datafono: int
    total_fiado: int
    total_voided: int
    total_internal_use: int
    physical_cash: int
    difference: int
    notes: Optional[str] = None
    created_at: str
