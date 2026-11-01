import os

DEV_SECRET_KEY = "super-secret-key-for-dev-only-12345"


class Settings:
    PROJECT_NAME: str = "Toscana Pastry"
    # "dev" (default) or "prod". In prod, validate_startup refuses unsafe config.
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev").strip().lower()
    SECRET_KEY: str = os.getenv("SECRET_KEY", DEV_SECRET_KEY)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day
    # Mercado Pago (Checkout Pro). Empty = payments unavailable (503).
    MP_ACCESS_TOKEN: str = os.getenv("MP_ACCESS_TOKEN", "")
    MP_WEBHOOK_SECRET: str = os.getenv("MP_WEBHOOK_SECRET", "")
    MP_NOTIFICATION_URL: str = os.getenv("MP_NOTIFICATION_URL", "")
    MP_BACK_URL: str = os.getenv("MP_BACK_URL", "")

settings = Settings()


def validate_startup(current: Settings = settings) -> None:
    """Refuse to start in prod with the dev SECRET_KEY or no webhook secret."""
    if current.ENVIRONMENT != "prod":
        return
    problems = []
    if current.SECRET_KEY == DEV_SECRET_KEY:
        problems.append("SECRET_KEY is the dev default")
    if not current.MP_WEBHOOK_SECRET:
        problems.append("MP_WEBHOOK_SECRET is missing")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
