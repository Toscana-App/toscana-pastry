import pytest

from core.config import DEFAULT_DEV_SECRET_KEY, Settings


def _settings(monkeypatch, environment, secret=None):
    monkeypatch.setattr(Settings, "ENVIRONMENT", environment)
    monkeypatch.setattr(Settings, "SECRET_KEY", secret or DEFAULT_DEV_SECRET_KEY)
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
