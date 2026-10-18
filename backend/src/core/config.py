import os

class Settings:
    PROJECT_NAME: str = "Toscana Pastry"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-for-dev-only-12345")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day
    # Fase 8 (P9): base pública para los links firmados del PDF (se
    # arman en wa.me y en el link temporal). En producción: el dominio
    # real de la app.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

settings = Settings()
