from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.database import supabase
from app.auth import get_current_user, require_role

router = APIRouter()


class CategoryCreate(BaseModel):
    name: str


@router.get("/")
async def list_categories(user=Depends(get_current_user)):
    result = (
        supabase.table("categories")
        .select("*")
        .order("name")
        .execute()
    )
    return result.data


@router.post("/", status_code=201)
async def create_category(
    data: CategoryCreate, user=Depends(require_role("owner", "admin"))
):
    try:
        result = (
            supabase.table("categories")
            .insert({"name": data.name})
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=400, detail="Error al crear la categoría"
        )

    return result.data[0]
