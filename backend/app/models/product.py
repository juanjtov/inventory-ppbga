from pydantic import BaseModel
from typing import Optional


class ProductCreate(BaseModel):
    name: str
    category_id: str
    supplier_id: str
    sale_price: int
    purchase_price: int = 0
    stock: Optional[int] = None
    min_stock_alert: int = 5
    type: str = "product"  # product or service


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[str] = None
    supplier_id: Optional[str] = None
    sale_price: Optional[int] = None
    purchase_price: Optional[int] = None
    stock: Optional[int] = None
    min_stock_alert: Optional[int] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None


class PriceUpdate(BaseModel):
    sale_price: int


class ProductResponse(BaseModel):
    id: str
    name: str
    category_id: str
    supplier_id: str
    sale_price: int
    purchase_price: int
    stock: Optional[int]
    min_stock_alert: int
    type: str
    is_active: bool
    created_at: str
    updated_at: str
    category_name: Optional[str] = None
    supplier_name: Optional[str] = None
    is_low_stock: Optional[bool] = None
