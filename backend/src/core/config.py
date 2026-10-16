import os

class Settings:
    PROJECT_NAME: str = "Toscana Pastry"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-for-dev-only-12345")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day

settings = Settings()
