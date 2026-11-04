import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.admin.router import router as admin_router
from api.v1.auth.router import router as auth_router
from api.v1.budgets.router import router as budgets_router
from api.v1.calc.router import router as calc_router
from api.v1.cart.router import router as cart_router
from api.v1.coupons.router import router as coupons_router
from api.v1.customers.router import router as customers_router
from api.v1.ingredients.router import router as ingredients_router
from api.v1.imports.router import router as imports_router
from api.v1.leads.router import router as leads_router
from api.v1.orders.router import router as orders_router
from api.v1.pdf.router import router as pdf_router
from api.v1.pricing.router import router as pricing_router
from api.v1.products.router import router as products_router
from api.v1.settings.router import router as settings_router
from api.v1.webhooks.router import router as webhooks_router
from api.v1.whatsapp.router import router as whatsapp_router
from data.db import init_db
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast when the config is not safe for the environment.
    app_settings.validate_for_startup()
    # Idempotent: creates accent_fold and the schema if missing.
    await init_db(Base)
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
app.include_router(imports_router, prefix="/api/v1")
app.include_router(cart_router, prefix="/api/v1")
app.include_router(coupons_router, prefix="/api/v1")
app.include_router(leads_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(whatsapp_router, prefix="/api/v1")

app.include_router(budgets_router, prefix="/api/v1")
# El router de PDF ya lleva sus prefijos internos (/budgets/.../pdf y /pdf/...).
app.include_router(pdf_router, prefix="/api/v1")

app.include_router(calc_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "healthy"}
