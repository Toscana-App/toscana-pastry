
from fastapi import FastAPI
from api.v1.auth.router import router as auth_router

app = FastAPI(title="Toscana Pastry API")

app.include_router(auth_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "healthy"}
