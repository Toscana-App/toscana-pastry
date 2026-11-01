import os

DEFAULT_DEV_SECRET_KEY = "super-secret-key-for-dev-only-12345"


class Settings:
    PROJECT_NAME: str = "Toscana Pastry"
    # "dev" (default) o "prod". En prod el arranque falla si SECRET_KEY es
    # el valor por defecto (ver validate_for_startup).
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev").strip().lower()
    SECRET_KEY: str = os.getenv("SECRET_KEY", DEFAULT_DEV_SECRET_KEY)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day
    # Fase 8 (P9): base pública para los links firmados del PDF (se
    # arman en wa.me y en el link temporal). En producción: el dominio
    # real de la app.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

    def validate_for_startup(self) -> None:
        """Rechaza arrancar en prod con el SECRET_KEY de desarrollo
        (permitiría forjar JWT y links firmados de PDF)."""
        if self.ENVIRONMENT not in ("dev", "prod"):
            raise RuntimeError(
                f"ENVIRONMENT inválido: {self.ENVIRONMENT!r} (usar 'dev' o 'prod')"
            )
        if self.ENVIRONMENT == "prod" and self.SECRET_KEY == DEFAULT_DEV_SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY por defecto no permitido con ENVIRONMENT=prod: "
                "definí un SECRET_KEY propio"
            )


settings = Settings()
