from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.auth.router import router as auth_router
from api.v1.admin.router import router as admin_router
from api.v1.settings.router import router as settings_router
from api.v1.pricing.router import router as pricing_router
from api.v1.ingredients.router import router as ingredients_router
from api.v1.calc.router import router as calc_router
from api.v1.products.router import router as products_router
from core.config import settings
from data.db import engine
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
    settings.validate()
    # create_all es idempotente: crea el esquema si falta y no toca lo existente.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
app.include_router(calc_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "healthy"}
