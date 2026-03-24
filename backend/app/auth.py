from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    try:
        auth_response = supabase.auth.get_user(token)
        auth_user = auth_response.user
        if not auth_user:
            raise HTTPException(status_code=401, detail="Token inválido")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

    result = (
        supabase.table("users")
        .select("*")
        .eq("auth_id", auth_user.id)
        .eq("is_active", True)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=401, detail="Usuario no encontrado o inactivo"
        )
    return result.data


def require_role(*roles):
    async def role_checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Permiso denegado")
        return user

    return role_checker
