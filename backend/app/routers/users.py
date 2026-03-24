from fastapi import APIRouter, Depends, HTTPException
from app.database import supabase
from app.auth import require_role
from app.models.user import UserCreate, UserUpdate

router = APIRouter()


@router.get("/")
async def list_users(user=Depends(require_role("owner"))):
    result = supabase.table("users").select("*").execute()
    return result.data


@router.post("/", status_code=201)
async def create_user(
    data: UserCreate, user=Depends(require_role("owner"))
):
    if data.role == "owner":
        raise HTTPException(
            status_code=400, detail="No se puede crear un usuario con rol de propietario"
        )

    try:
        auth_response = supabase.auth.admin.create_user(
            {
                "email": data.email,
                "password": data.password,
                "email_confirm": True,
            }
        )
    except Exception:
        raise HTTPException(
            status_code=400, detail="Error al crear el usuario en autenticación"
        )

    auth_user = auth_response.user
    if not auth_user:
        raise HTTPException(
            status_code=400, detail="Error al crear el usuario en autenticación"
        )

    try:
        result = (
            supabase.table("users")
            .insert(
                {
                    "auth_id": auth_user.id,
                    "email": data.email,
                    "full_name": data.full_name,
                    "role": data.role,
                }
            )
            .execute()
        )
    except Exception:
        supabase.auth.admin.delete_user(auth_user.id)
        raise HTTPException(
            status_code=400, detail="Error al guardar el usuario en la base de datos"
        )

    return result.data[0]


@router.put("/{id}")
async def update_user(
    id: str, data: UserUpdate, user=Depends(require_role("owner"))
):
    if data.role and user["id"] == id:
        raise HTTPException(
            status_code=400, detail="No puedes cambiar tu propio rol"
        )

    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            status_code=400, detail="No se proporcionaron datos para actualizar"
        )

    try:
        result = (
            supabase.table("users")
            .update(update_data)
            .eq("id", id)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=400, detail="Error al actualizar el usuario"
        )

    if not result.data:
        raise HTTPException(
            status_code=404, detail="Usuario no encontrado"
        )

    return result.data[0]


@router.put("/{id}/deactivate")
async def deactivate_user(
    id: str, user=Depends(require_role("owner"))
):
    if user["id"] == id:
        raise HTTPException(
            status_code=400, detail="No puedes desactivarte a ti mismo"
        )

    try:
        result = (
            supabase.table("users")
            .update({"is_active": False})
            .eq("id", id)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=400, detail="Error al desactivar el usuario"
        )

    if not result.data:
        raise HTTPException(
            status_code=404, detail="Usuario no encontrado"
        )

    return result.data[0]


@router.delete("/{id}")
async def delete_user(
    id: str, user=Depends(require_role("owner"))
):
    if user["id"] == id:
        raise HTTPException(
            status_code=400, detail="No puedes eliminarte a ti mismo"
        )

    # Get the user to find auth_id
    try:
        target = (
            supabase.table("users")
            .select("*")
            .eq("id", id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not target.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if target.data["role"] == "owner":
        raise HTTPException(
            status_code=400, detail="No se puede eliminar un usuario propietario"
        )

    # Check user has no sales (FK constraint)
    sales = (
        supabase.table("sales")
        .select("id")
        .eq("user_id", id)
        .limit(1)
        .execute()
    )
    if sales.data:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar un usuario con ventas registradas. Desactivelo en su lugar.",
        )

    # Delete from users table first
    try:
        supabase.table("users").delete().eq("id", id).execute()
    except Exception:
        raise HTTPException(
            status_code=400, detail="Error al eliminar el usuario de la base de datos"
        )

    # Delete from Supabase Auth
    try:
        supabase.auth.admin.delete_user(target.data["auth_id"])
    except Exception:
        pass  # Auth cleanup is best-effort

    return {"message": "Usuario eliminado correctamente"}
