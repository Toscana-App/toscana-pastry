from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.v1.auth.router import router as auth_router
from api.v1.admin.router import router as admin_router
from api.v1.settings.router import router as settings_router
from api.v1.pricing.router import router as pricing_router
from api.v1.ingredients.router import router as ingredients_router
from api.v1.products.router import router as products_router
from api.v1.customers.router import router as customers_router
from api.v1.orders.router import router as orders_router
from api.v1.budgets.router import router as budgets_router
from api.v1.pdf.router import router as pdf_router



from api.v1.calc.router import router as calc_router
from api.v1.products.router import router as products_router
from data.db import engine
from core.config import settings as app_settings
from data.models import Base

# El frontend llama a la API desde otro origen (puerto distinto), así que el
# navegador exige CORS. Orígenes explícitos: con allow_credentials=True no se
# admite "*". Configurable por env para staging/producción.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]


def _ensure_phase8_columns(sync_conn):
    """Fase 8: columnas nuevas de business_settings para BDs ya creadas
    (create_all no hace ALTER). Solo SQLite: es la base de la app hoy."""
    if sync_conn.dialect.name != "sqlite":
        return
    rows = sync_conn.execute(
        text("PRAGMA table_info(business_settings)")
    ).fetchall()
    existing = {row[1] for row in rows}
    if "business_name" not in existing:
        sync_conn.execute(
            text(
                "ALTER TABLE business_settings "
                "ADD COLUMN business_name VARCHAR NOT NULL DEFAULT ''"
            )
        )
    if "footer_text" not in existing:
        sync_conn.execute(
            text(
                "ALTER TABLE business_settings "
                "ADD COLUMN footer_text VARCHAR NOT NULL DEFAULT ''"
            )
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Falla rápido si la config no es segura para el entorno.
    app_settings.validate_for_startup()
    # create_all es idempotente: crea el esquema si falta y no toca lo existente.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Fase 8 (P9): branding del PDF en BDs anteriores (idempotente).
        await conn.run_sync(_ensure_phase8_columns)
    yield


app = FastAPI(title="Toscana Pastry API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(pricing_router, prefix="/api/v1")
app.include_router(ingredients_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(budgets_router, prefix="/api/v1")
# El router de PDF ya lleva sus prefijos internos (/budgets/.../pdf y /pdf/...).
app.include_router(pdf_router, prefix="/api/v1")

app.include_router(calc_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "healthy"}
