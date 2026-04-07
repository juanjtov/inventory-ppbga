from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.database import supabase
from app.auth import get_current_user, require_role

router = APIRouter()


class SupplierCreate(BaseModel):
    name: str


@router.get("")
async def list_suppliers(user=Depends(get_current_user)):
    result = (
        supabase.table("suppliers")
        .select("*")
        .order("name")
        .execute()
    )
    return result.data


@router.post("", status_code=201)
async def create_supplier(
    data: SupplierCreate, user=Depends(require_role("owner", "admin"))
):
    try:
        result = (
            supabase.table("suppliers")
            .insert({"name": data.name})
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=400, detail="Error al crear el proveedor"
        )

    return result.data[0]
