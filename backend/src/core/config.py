import os

DEFAULT_DEV_SECRET_KEY = "super-secret-key-for-dev-only-12345"
DEFAULT_DEV_REFRESH_SECRET_KEY = "refresh-secret-key-for-dev-only-67890"
# Backwards-compatible alias.
DEV_SECRET_KEY = DEFAULT_DEV_SECRET_KEY


class Settings:
    PROJECT_NAME: str = "Toscana Pastry"
    # "dev" (default) or "prod". In prod, validate_for_startup refuses unsafe config.
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev").strip().lower()
    SECRET_KEY: str = os.getenv("SECRET_KEY", DEFAULT_DEV_SECRET_KEY)
    # Refresh tokens are signed with their own key: leaking one secret does
    # not let an attacker mint the other token type.
    REFRESH_SECRET_KEY: str = os.getenv(
        "REFRESH_SECRET_KEY", DEFAULT_DEV_REFRESH_SECRET_KEY
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    # Mercado Pago (Checkout Pro). Empty = payments unavailable (503).
    MP_ACCESS_TOKEN: str = os.getenv("MP_ACCESS_TOKEN", "")
    MP_WEBHOOK_SECRET: str = os.getenv("MP_WEBHOOK_SECRET", "")
    MP_NOTIFICATION_URL: str = os.getenv("MP_NOTIFICATION_URL", "")
    MP_BACK_URL: str = os.getenv("MP_BACK_URL", "")
    # Fase 8 (P9): base pública para los links firmados del PDF (se
    # arman en wa.me y en el link temporal). En producción: el dominio
    # real de la app.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    # Servicio de PDF (pdfgenerator, ADR-0001): base URL HTTP del binario que
    # renderiza presupuesto, reportes y pricelist. Sin él esos endpoints
    # devuelven 503 controlado (PdfServiceError).
    PDFGEN_URL: str = os.getenv("PDFGEN_URL", "http://localhost:8100")

    def validate_for_startup(self) -> None:
        """Refuse to start with an invalid ENVIRONMENT, or in prod with the
        dev SECRET_KEY / REFRESH_SECRET_KEY (forgeable JWT / signed PDF
        links), a refresh key equal to the access key, or without the
        Mercado Pago webhook secret."""
        if self.ENVIRONMENT not in ("dev", "prod"):
            raise RuntimeError(
                f"ENVIRONMENT inválido: {self.ENVIRONMENT!r} (usar 'dev' o 'prod')"
            )
        if self.ENVIRONMENT != "prod":
            return
        problems = []
        if self.SECRET_KEY == DEFAULT_DEV_SECRET_KEY:
            problems.append("SECRET_KEY is the dev default")
        if self.REFRESH_SECRET_KEY == DEFAULT_DEV_REFRESH_SECRET_KEY:
            problems.append("REFRESH_SECRET_KEY is the dev default")
        elif self.REFRESH_SECRET_KEY == self.SECRET_KEY:
            problems.append("REFRESH_SECRET_KEY must differ from SECRET_KEY")
        if not self.MP_WEBHOOK_SECRET:
            problems.append("MP_WEBHOOK_SECRET is missing")
        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


settings = Settings()


def validate_startup(current: Settings = settings) -> None:
    """Module-level entry point; delegates to Settings.validate_for_startup."""
    current.validate_for_startup()
