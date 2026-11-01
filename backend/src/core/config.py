import os

_DEV_SECRET_KEY = "super-secret-key-for-dev-only-12345"


class Settings:
    PROJECT_NAME: str = "Toscana Pastry"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev")  # "dev" (default) | "prod"
    SECRET_KEY: str = os.getenv("SECRET_KEY", _DEV_SECRET_KEY)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day

    def validate(self) -> None:
        """Refuse to start in prod with the dev default secret."""
        if self.ENVIRONMENT == "prod" and self.SECRET_KEY == _DEV_SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY must be set to a non-default value when ENVIRONMENT=prod"
            )


settings = Settings()
