"""Production startup validation (ENVIRONMENT flag)."""

import pytest

from core.config import DEV_SECRET_KEY, Settings, validate_startup


def _settings(**kw) -> Settings:
    s = Settings()
    s.ENVIRONMENT = "dev"
    s.SECRET_KEY = "a-real-secret"
    s.MP_WEBHOOK_SECRET = "whsec"
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_environment_defaults_to_dev(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    import importlib

    import core.config as cfg

    assert importlib.reload(cfg).Settings.ENVIRONMENT == "dev"


def test_dev_allows_defaults():
    validate_startup(_settings(SECRET_KEY=DEV_SECRET_KEY, MP_WEBHOOK_SECRET=""))


def test_prod_refuses_dev_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_startup(_settings(ENVIRONMENT="prod", SECRET_KEY=DEV_SECRET_KEY))


def test_prod_refuses_missing_webhook_secret():
    with pytest.raises(RuntimeError, match="MP_WEBHOOK_SECRET"):
        validate_startup(_settings(ENVIRONMENT="prod", MP_WEBHOOK_SECRET=""))


def test_prod_with_safe_config_starts():
    validate_startup(_settings(ENVIRONMENT="prod"))
