import os

class Settings:
    PROJECT_NAME: str = "Toscana Pastry"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-for-dev-only-12345")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day
    # Mercado Pago (Checkout Pro). Empty = payments unavailable (503).
    MP_ACCESS_TOKEN: str = os.getenv("MP_ACCESS_TOKEN", "")
    MP_WEBHOOK_SECRET: str = os.getenv("MP_WEBHOOK_SECRET", "")
    MP_NOTIFICATION_URL: str = os.getenv("MP_NOTIFICATION_URL", "")
    MP_BACK_URL: str = os.getenv("MP_BACK_URL", "")

settings = Settings()
