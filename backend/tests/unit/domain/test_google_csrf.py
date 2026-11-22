from domain.auth.google import google_json_flow_csrf_trusted

ALLOWED = ["http://localhost:3000"]


def test_same_origin_sec_fetch_site_is_trusted():
    assert (
        google_json_flow_csrf_trusted("same-origin", None, ALLOWED) is True
    )


def test_same_origin_with_any_origin_is_trusted():
    assert (
        google_json_flow_csrf_trusted(
            "same-origin", "http://evil.example", ALLOWED
        )
        is True
    )


def test_cross_site_is_rejected_even_with_allowed_origin():
    assert (
        google_json_flow_csrf_trusted(
            "cross-site", "http://localhost:3000", ALLOWED
        )
        is False
    )


def test_same_site_is_rejected_even_with_allowed_origin():
    assert (
        google_json_flow_csrf_trusted(
            "same-site", "http://localhost:3000", ALLOWED
        )
        is False
    )


def test_none_is_rejected_even_with_allowed_origin():
    assert (
        google_json_flow_csrf_trusted("none", "http://localhost:3000", ALLOWED)
        is False
    )


def test_missing_sec_fetch_site_with_exact_allowed_origin_is_trusted():
    # Fail-safe for non-sec-fetch browsers: exact Origin match only.
    assert google_json_flow_csrf_trusted(None, "http://localhost:3000", ALLOWED) is True


def test_missing_sec_fetch_site_with_other_origin_is_rejected():
    assert google_json_flow_csrf_trusted(None, "http://evil.example", ALLOWED) is False


def test_missing_sec_fetch_site_without_origin_is_rejected():
    assert google_json_flow_csrf_trusted(None, None, ALLOWED) is False


def test_unknown_sec_fetch_site_value_is_rejected():
    assert (
        google_json_flow_csrf_trusted("weird", "http://localhost:3000", ALLOWED)
        is False
    )
