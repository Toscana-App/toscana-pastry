from core.config import Settings, _parse_google_auto_create


class _FakeSettings:

    def __init__(self, flag, environment):
        self.GOOGLE_AUTO_CREATE = flag
        self.ENVIRONMENT = environment


def _resolve(flag, environment):
    getter = Settings.__dict__["google_auto_create"].fget
    assert getter is not None
    return getter(_FakeSettings(flag, environment))


def test_parse_none_and_empty_and_garbage_resolve_to_none():
    assert _parse_google_auto_create(None) is None
    assert _parse_google_auto_create("") is None
    assert _parse_google_auto_create("   ") is None
    assert _parse_google_auto_create("maybe") is None


def test_parse_true_spellings():
    for value in ("1", "true", "TRUE", "True", "yes", "on"):
        assert _parse_google_auto_create(value) is True, value


def test_parse_false_spellings():
    for value in ("0", "false", "FALSE", "no", "off"):
        assert _parse_google_auto_create(value) is False, value


def test_unset_flag_resolves_to_not_prod():
    assert _resolve(None, "dev") is True
    assert _resolve(None, "staging") is True
    assert _resolve(None, "prod") is False


def test_explicit_flag_wins_over_environment():
    assert _resolve(True, "prod") is True
    assert _resolve(False, "dev") is False
