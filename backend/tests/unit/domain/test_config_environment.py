import pytest

from core.config import Settings, DEFAULT_DEV_SECRET_KEY


def _settings(env: str, key: str, mp: str = "") -> Settings:
    s = Settings()
    s.MP_WEBHOOK_SECRET = mp
    s.ENVIRONMENT = env
    s.SECRET_KEY = key
    return s


def test_dev_allows_default_secret():
    _settings("dev", DEFAULT_DEV_SECRET_KEY).validate_for_startup()


def test_prod_with_default_secret_refuses_to_start():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _settings("prod", DEFAULT_DEV_SECRET_KEY).validate_for_startup()


def test_prod_with_custom_secret_starts():
    _settings("prod", "a-real-secret", mp="whsec").validate_for_startup()
