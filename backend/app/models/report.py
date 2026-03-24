from pydantic import BaseModel
from typing import Optional, List


class DailySummary(BaseModel):
    date: str
    total_sales: int
    total_sales_count: int
    by_payment_method: dict
    fiado_pending: int
    voided_count: int
    internal_use_count: int
    top_products: list


class TopSellerItem(BaseModel):
    product_id: str
    product_name: str
    units_sold: int
    revenue: int


class InventoryValueItem(BaseModel):
    product_id: str
    name: str
    stock: int
    sale_price: int
    purchase_price: int
    total_sale_value: int
    total_purchase_value: int


class InventoryValueResponse(BaseModel):
    items: List[InventoryValueItem]
    grand_total_sale: int
    grand_total_purchase: int


class ReconciliationItem(BaseModel):
    product_id: str
    name: str
    expected_stock: int
    actual_stock: int
    difference: int


class FiadoAgingBucket(BaseModel):
    label: str
    count: int
    total: int


class FiadoAgingResponse(BaseModel):
    total_owed: int
    total_count: int
    buckets: List[FiadoAgingBucket]
