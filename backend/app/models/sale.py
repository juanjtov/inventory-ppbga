from pydantic import BaseModel
from typing import Optional, List


class SaleItemCreate(BaseModel):
    product_id: str
    quantity: int


class PaymentSplit(BaseModel):
    payment_method: str  # efectivo | datafono | transferencia (never fiado/mixto)
    amount: int


class SaleCreate(BaseModel):
    items: List[SaleItemCreate]
    payment_method: str  # efectivo, transferencia, datafono, fiado, mixto
    client_name: Optional[str] = None
    notes: Optional[str] = None
    payments: Optional[List[PaymentSplit]] = None  # required when payment_method == 'mixto'


class AddItemsRequest(BaseModel):
    items: List[SaleItemCreate]


class RemoveItemRequest(BaseModel):
    item_id: str


class VoidSale(BaseModel):
    reason: str


class PaySale(BaseModel):
    # Exactly one of these must be provided.
    payment_method: Optional[str] = None  # efectivo | datafono | transferencia (never fiado)
    payments: Optional[List[PaymentSplit]] = None  # for split settlements


class SaleItemResponse(BaseModel):
    id: str
    product_id: str
    quantity: int
    unit_price: int
    subtotal: int
    product_name: Optional[str] = None


class SalePaymentResponse(BaseModel):
    id: str
    payment_method: str
    amount: int
    paid_at: str


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
    paid_payment_method: Optional[str] = None
    paid_at: Optional[str] = None
    items: Optional[List[SaleItemResponse]] = None
    payments: Optional[List[SalePaymentResponse]] = None
    user_name: Optional[str] = None
