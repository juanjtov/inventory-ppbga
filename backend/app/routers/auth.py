from fastapi import APIRouter, Depends, HTTPException
from app.database import supabase, supabase_auth_client
from app.auth import get_current_user
from app.models.user import LoginRequest

router = APIRouter()


@router.post("/login")
async def login(request: LoginRequest):
    try:
        auth_response = supabase_auth_client.auth.sign_in_with_password(
            {"email": request.email, "password": request.password}
        )
    except Exception as e:
        raise HTTPException(
            status_code=401, detail="Credenciales inválidas"
        )

    if not auth_response.user:
        raise HTTPException(
            status_code=401, detail="Credenciales inválidas"
        )

    if not auth_response.session:
        raise HTTPException(
            status_code=401, detail="No se pudo crear la sesión"
        )

    try:
        result = (
            supabase.table("users")
            .select("*")
            .eq("auth_id", str(auth_response.user.id))
            .eq("is_active", True)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=401, detail="Usuario no encontrado o inactivo"
        )

    if not result.data:
        raise HTTPException(
            status_code=401, detail="Usuario no encontrado o inactivo"
        )

    return {
        "access_token": auth_response.session.access_token,
        "user": result.data,
    }


@router.post("/logout")
async def logout(user=Depends(get_current_user)):
    try:
        supabase.auth.sign_out()
    except Exception:
        raise HTTPException(
            status_code=500, detail="Error al cerrar sesión"
        )
    return {"message": "Sesión cerrada correctamente"}


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return user
