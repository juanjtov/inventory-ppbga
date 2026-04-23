import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import (
    auth,
    users,
    products,
    sales,
    inventory,
    reports,
    categories,
    suppliers,
    audit_log,
    stock_adjustments,
)

app = FastAPI(title="Premier Padel BGA - Inventario", version="1.0.0")

# Guardrail log: print which Supabase project this process is talking to.
# Single best defense against pointing local dev at prod (or vice versa).
_logger = logging.getLogger("uvicorn.error")
_project_ref = settings.supabase_url.split("//")[-1].split(".")[0]
_logger.info("Supabase project: %s (%s)", _project_ref, settings.supabase_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(products.router, prefix="/api/v1/products", tags=["Products"])
app.include_router(sales.router, prefix="/api/v1/sales", tags=["Sales"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(
    categories.router, prefix="/api/v1/categories", tags=["Categories"]
)
app.include_router(suppliers.router, prefix="/api/v1/suppliers", tags=["Suppliers"])
app.include_router(
    audit_log.router, prefix="/api/v1/audit-log", tags=["Audit Log"]
)
app.include_router(
    stock_adjustments.router,
    prefix="/api/v1/stock-adjustments",
    tags=["Stock Adjustments"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
