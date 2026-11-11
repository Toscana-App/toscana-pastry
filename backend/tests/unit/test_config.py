import pytest

from core.config import DEFAULT_DEV_REFRESH_SECRET_KEY, DEFAULT_DEV_SECRET_KEY, Settings


def _settings(monkeypatch, environment, secret=None):
    monkeypatch.setattr(Settings, "REFRESH_SECRET_KEY", "r" * 40)
    monkeypatch.setattr(Settings, "MP_WEBHOOK_SECRET", "whsec")
    monkeypatch.setattr(Settings, "ENVIRONMENT", environment)
    monkeypatch.setattr(Settings, "SECRET_KEY", secret or DEFAULT_DEV_SECRET_KEY)
    monkeypatch.setattr(Settings, "AFIP_ENV", "prod")
    monkeypatch.setattr(Settings, "AFIP_PRIVATE_KEY_PATH", "/run/secrets/afip_key.pem")
    monkeypatch.setattr(Settings, "AFIP_CERT_PATH", "/run/secrets/afip_cert.pem")
    return Settings()


def test_prod_con_secret_por_defecto_no_arranca(monkeypatch):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _settings(monkeypatch, "prod").validate_for_startup()


def test_prod_con_secret_propio_arranca(monkeypatch):
    _settings(monkeypatch, "prod", "x" * 40).validate_for_startup()


def test_dev_con_secret_por_defecto_arranca(monkeypatch):
    _settings(monkeypatch, "dev").validate_for_startup()


def test_environment_invalido_no_arranca(monkeypatch):
    with pytest.raises(RuntimeError, match="ENVIRONMENT"):
        _settings(monkeypatch, "staging").validate_for_startup()


def test_prod_con_refresh_secret_por_defecto_no_arranca(monkeypatch):
    settings = _settings(monkeypatch, "prod", "x" * 40)
    monkeypatch.setattr(Settings, "REFRESH_SECRET_KEY", DEFAULT_DEV_REFRESH_SECRET_KEY)
    with pytest.raises(RuntimeError, match="REFRESH_SECRET_KEY"):
        settings.validate_for_startup()


def test_prod_con_refresh_secret_igual_al_access_no_arranca(monkeypatch):
    settings = _settings(monkeypatch, "prod", "x" * 40)
    monkeypatch.setattr(Settings, "REFRESH_SECRET_KEY", "x" * 40)
    with pytest.raises(RuntimeError, match="REFRESH_SECRET_KEY"):
        settings.validate_for_startup()
