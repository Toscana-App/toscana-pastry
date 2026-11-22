import os

DEFAULT_DEV_SECRET_KEY = "super-secret-key-for-dev-only-12345"
DEFAULT_DEV_REFRESH_SECRET_KEY = "refresh-secret-key-for-dev-only-67890"
DEV_SECRET_KEY = DEFAULT_DEV_SECRET_KEY

AFIP_ENV_HOMOLOGACION = "homo"
AFIP_ENV_PRODUCCION = "prod"
AFIP_ENVIRONMENTS = (AFIP_ENV_HOMOLOGACION, AFIP_ENV_PRODUCCION)

AFIP_WSAA_URLS: dict[str, str] = {
    AFIP_ENV_HOMOLOGACION: "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL",
    AFIP_ENV_PRODUCCION: "https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL",
}
AFIP_WSFE_URLS: dict[str, str] = {
    AFIP_ENV_HOMOLOGACION: "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
    AFIP_ENV_PRODUCCION: "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL",
}



class Settings:
    PROJECT_NAME: str = "Toscana Pastry"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev").strip().lower()
    SECRET_KEY: str = os.getenv("SECRET_KEY", DEFAULT_DEV_SECRET_KEY)
    REFRESH_SECRET_KEY: str = os.getenv(
        "REFRESH_SECRET_KEY", DEFAULT_DEV_REFRESH_SECRET_KEY
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    MP_ACCESS_TOKEN: str = os.getenv("MP_ACCESS_TOKEN", "")
    MP_WEBHOOK_SECRET: str = os.getenv("MP_WEBHOOK_SECRET", "")
    MP_NOTIFICATION_URL: str = os.getenv("MP_NOTIFICATION_URL", "")
    MP_BACK_URL: str = os.getenv("MP_BACK_URL", "")
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    PDFGEN_URL: str = os.getenv("PDFGEN_URL", "http://localhost:8100")
    MEDIA_ROOT: str = os.getenv(
        "MEDIA_ROOT",
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "media")
        ),
    )
    AFIP_ENV: str = (os.getenv("AFIP_ENV") or AFIP_ENV_HOMOLOGACION).strip().lower()
    AFIP_PRIVATE_KEY_PATH: str = os.getenv("AFIP_PRIVATE_KEY_PATH", "")
    AFIP_CERT_PATH: str = os.getenv("AFIP_CERT_PATH", "")
    AFIP_PRIVATE_KEY_PEM: str = os.getenv("AFIP_PRIVATE_KEY_PEM", "")
    AFIP_CERT_PEM: str = os.getenv("AFIP_CERT_PEM", "")
    AFIP_WSAA_URL: str = os.getenv("AFIP_WSAA_URL", "")
    AFIP_WSFE_URL: str = os.getenv("AFIP_WSFE_URL", "")

    @property
    def afip_wsaa_url(self) -> str:
        return self.AFIP_WSAA_URL.strip() or AFIP_WSAA_URLS.get(
            self.AFIP_ENV, AFIP_WSAA_URLS[AFIP_ENV_HOMOLOGACION]
        )

    @property
    def afip_wsfe_url(self) -> str:
        return self.AFIP_WSFE_URL.strip() or AFIP_WSFE_URLS.get(
            self.AFIP_ENV, AFIP_WSFE_URLS[AFIP_ENV_HOMOLOGACION]
        )

    @property
    def afip_credentials_configured(self) -> bool:
        has_paths = bool(self.AFIP_PRIVATE_KEY_PATH.strip()) and bool(
            self.AFIP_CERT_PATH.strip()
        )
        has_pem = bool(self.AFIP_PRIVATE_KEY_PEM.strip()) and bool(
            self.AFIP_CERT_PEM.strip()
        )
        return has_paths or has_pem

    def validate_afip(self, problems: list[str]) -> None:
        if self.AFIP_ENV not in AFIP_ENVIRONMENTS:
            problems.append(
                f"AFIP_ENV inválido: {self.AFIP_ENV!r} (usar 'homo' o 'prod')"
            )
            return
        if self.ENVIRONMENT != "prod":
            return
        if self.AFIP_ENV != AFIP_ENV_PRODUCCION:
            problems.append("AFIP_ENV must be 'prod' in production")
        if not self.afip_credentials_configured:
            problems.append(
                "AFIP_PRIVATE_KEY_PATH/AFIP_CERT_PATH (o AFIP_*_PEM) is missing"
            )

    def validate_for_startup(self) -> None:
        if self.ENVIRONMENT not in ("dev", "prod"):
            raise RuntimeError(
                f"ENVIRONMENT inválido: {self.ENVIRONMENT!r} (usar 'dev' o 'prod')"
            )
        if self.AFIP_ENV not in AFIP_ENVIRONMENTS:
            raise RuntimeError(
                f"AFIP_ENV inválido: {self.AFIP_ENV!r} (usar 'homo' o 'prod')"
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
        self.validate_afip(problems)
        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))



settings = Settings()


def validate_startup(current: Settings = settings) -> None:
    current.validate_for_startup()
