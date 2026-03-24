from pydantic import BaseModel
from typing import Optional, List


class SaleItemCreate(BaseModel):
    product_id: str
    quantity: int


class SaleCreate(BaseModel):
    items: List[SaleItemCreate]
    payment_method: str  # efectivo, transferencia, datafono, fiado
    client_name: Optional[str] = None
    notes: Optional[str] = None


class VoidSale(BaseModel):
    reason: str


class SaleItemResponse(BaseModel):
    id: str
    product_id: str
    quantity: int
    unit_price: int
    subtotal: int
    product_name: Optional[str] = None


class SaleResponse(BaseModel):
    id: str
    user_id: str
    total: int
    payment_method: str
    status: str
    client_name: Optional[str] = None
    notes: Optional[str] = None
    voided_by: Optional[str] = None
    void_reason: Optional[str] = None
    created_at: str
    voided_at: Optional[str] = None
    items: Optional[List[SaleItemResponse]] = None
    user_name: Optional[str] = None
