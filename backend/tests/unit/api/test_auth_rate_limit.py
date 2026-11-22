"""The whole auth surface must share its own limiter instance.

Kept separate from the public PDF limiter so rate-limiting one does not
starve the other (decision 9).
"""
from api.v1.auth.router import auth_limiter
from api.v1.pdf.router import public_pdf_limiter


def test_auth_limiter_is_distinct_from_pdf_limiter():
    assert auth_limiter is not public_pdf_limiter


def test_auth_limiter_window_and_budget():
    assert auth_limiter.max_requests == 30
    assert auth_limiter.window_seconds == 120


def test_auth_limiter_exhausts_after_budget_then_resets():
    auth_limiter.reset()
    try:
        assert all(auth_limiter.allow("tester") for _ in range(30))
        assert auth_limiter.allow("tester") is False
    finally:
        auth_limiter.reset()
