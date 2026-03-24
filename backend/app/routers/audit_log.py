from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.database import supabase
from app.auth import require_role

router = APIRouter()


@router.get("/")
async def list_audit_logs(
    entity_type: Optional[str] = Query(
        None, description="Tipo de entidad (ej: product, sale)"
    ),
    entity_id: Optional[str] = Query(
        None, description="ID de la entidad"
    ),
    limit: int = Query(50, ge=1, le=500, description="Cantidad de registros"),
    offset: int = Query(0, ge=0, description="Desplazamiento"),
    user=Depends(require_role("owner")),
):
    try:
        query = (
            supabase.table("audit_log")
            .select("*, users(full_name)")
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )

        if entity_type:
            query = query.eq("entity_type", entity_type)
        if entity_id:
            query = query.eq("entity_id", entity_id)

        result = query.execute()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error al obtener los registros de auditoría",
        )

    return result.data
