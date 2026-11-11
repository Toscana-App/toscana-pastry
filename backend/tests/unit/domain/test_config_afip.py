"""T3 — Config AFIP por entorno (RNF-P13-02 / RNF-P13-03, decisión D4).

Homologación es el default; producción exige ``AFIP_ENV=prod`` explícito
y credenciales presentes al arrancar con ``ENVIRONMENT=prod``.
"""

import importlib

import pytest

import core.config as cfg
from core.config import (
    AFIP_ENVIRONMENTS,
    Settings,
    validate_startup,
)

HOMO_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
HOMO_WSFE = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
PROD_WSAA = "https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL"
PROD_WSFE = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"

AFIP_KEY_PATH = "/run/secrets/afip_private_key.pem"
AFIP_CERT_PATH = "/run/secrets/afip_certificate.pem"


def _settings(**overrides) -> Settings:
    s = Settings()
    s.ENVIRONMENT = "dev"
    s.SECRET_KEY = "a-real-secret"
    s.REFRESH_SECRET_KEY = "a-real-refresh-secret"
    s.MP_WEBHOOK_SECRET = "whsec"
    s.AFIP_ENV = "homo"
    s.AFIP_PRIVATE_KEY_PATH = ""
    s.AFIP_CERT_PATH = ""
    s.AFIP_PRIVATE_KEY_PEM = ""
    s.AFIP_CERT_PEM = ""
    s.AFIP_WSAA_URL = ""
    s.AFIP_WSFE_URL = ""
    for key, value in overrides.items():
        setattr(s, key, value)
    return s


def test_afip_env_defaults_to_homo(monkeypatch):
    monkeypatch.delenv("AFIP_ENV", raising=False)
    assert importlib.reload(cfg).Settings.AFIP_ENV == "homo"


def test_afip_environments_are_homo_and_prod():
    assert AFIP_ENVIRONMENTS == ("homo", "prod")


def test_urls_default_to_homologacion():
    s = _settings()
    assert s.afip_wsaa_url == HOMO_WSAA
    assert s.afip_wsfe_url == HOMO_WSFE


def test_urls_switch_to_production():
    s = _settings(AFIP_ENV="prod")
    assert s.afip_wsaa_url == PROD_WSAA
    assert s.afip_wsfe_url == PROD_WSFE


def test_url_overrides_win():
    s = _settings(
        AFIP_WSAA_URL="https://wsaa.internal/LoginCms?WSDL",
        AFIP_WSFE_URL="https://wsfe.internal/service.asmx?WSDL",
    )
    assert s.afip_wsaa_url == "https://wsaa.internal/LoginCms?WSDL"
    assert s.afip_wsfe_url == "https://wsfe.internal/service.asmx?WSDL"


def test_credentials_configured_with_paths():
    s = _settings(AFIP_PRIVATE_KEY_PATH=AFIP_KEY_PATH, AFIP_CERT_PATH=AFIP_CERT_PATH)
    assert s.afip_credentials_configured is True


def test_credentials_configured_with_pem():
    s = _settings(AFIP_PRIVATE_KEY_PEM="-----BEGIN PRIVATE KEY-----", AFIP_CERT_PEM="-----BEGIN CERTIFICATE-----")
    assert s.afip_credentials_configured is True


def test_credentials_missing():
    assert _settings().afip_credentials_configured is False


def test_dev_without_afip_credentials_starts():
    validate_startup(_settings())


def test_invalid_afip_env_fails_fast():
    with pytest.raises(RuntimeError, match="AFIP_ENV"):
        validate_startup(_settings(AFIP_ENV="homologacion"))


def test_prod_requires_explicit_afip_prod():
    with pytest.raises(RuntimeError, match="AFIP_ENV"):
        validate_startup(
            _settings(
                ENVIRONMENT="prod",
                AFIP_ENV="homo",
                AFIP_PRIVATE_KEY_PATH=AFIP_KEY_PATH,
                AFIP_CERT_PATH=AFIP_CERT_PATH,
            )
        )


def test_prod_requires_afip_credentials():
    with pytest.raises(RuntimeError, match="AFIP_PRIVATE_KEY_PATH"):
        validate_startup(_settings(ENVIRONMENT="prod", AFIP_ENV="prod"))


def test_prod_with_afip_prod_and_credentials_starts():
    validate_startup(
        _settings(
            ENVIRONMENT="prod",
            AFIP_ENV="prod",
            AFIP_PRIVATE_KEY_PATH=AFIP_KEY_PATH,
            AFIP_CERT_PATH=AFIP_CERT_PATH,
        )
    )


def test_startup_error_never_contains_paths():
    with pytest.raises(RuntimeError) as exc:
        validate_startup(_settings(ENVIRONMENT="prod", AFIP_ENV="prod"))
    assert AFIP_KEY_PATH not in str(exc.value)
