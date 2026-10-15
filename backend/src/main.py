from fastapi import FastAPI
from api.v1.auth.router import router as auth_router
from api.v1.admin.router import router as admin_router

app = FastAPI(title="Toscana Pastry API")

app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "healthy"}
