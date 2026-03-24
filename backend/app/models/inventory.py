from pydantic import BaseModel
from typing import Optional


class InventoryEntryCreate(BaseModel):
    product_id: str
    quantity: int
    supplier_id: str
    price_confirmed: bool = True
    actual_price: Optional[int] = None


class InternalUseCreate(BaseModel):
    product_id: str
    quantity: int
    reason: str


class MovementResponse(BaseModel):
    id: str
    type: str  # sale, entry, internal_use
    quantity: int
    date: str
    details: Optional[dict] = None
