from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import require_role
from app.models.inventory import InventoryEntryCreate, InternalUseCreate
from app.services.inventory_service import (
    create_entry,
    create_internal_use,
    get_movements,
)

router = APIRouter()


@router.post("/entry")
async def create_entry_endpoint(
    entry: InventoryEntryCreate,
    user=Depends(require_role("owner", "admin")),
):
    result = create_entry(entry, user)
    return result


@router.post("/internal-use")
async def create_internal_use_endpoint(
    internal_use: InternalUseCreate,
    user=Depends(require_role("owner", "admin")),
):
    result = create_internal_use(internal_use, user)
    return result


@router.get("/movements")
async def get_movements_endpoint(
    product_id: str = Query(..., description="ID del producto"),
    user=Depends(require_role("owner", "admin")),
):
    result = get_movements(product_id)
    return result
