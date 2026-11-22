from domain.auth.google import google_authoritative


def test_gmail_with_verified_email_is_authoritative():
    payload = {
        "sub": "123",
        "email": "user@GMAIL.com",
        "email_verified": True,
    }
    assert google_authoritative(payload) is True


def test_hd_workspace_claim_is_authoritative():
    payload = {
        "sub": "123",
        "email": "user@empresa.com",
        "hd": "empresa",
        "email_verified": True,
    }
    assert google_authoritative(payload) is True


def test_third_party_provider_is_not_authoritative():
    payload = {
        "sub": "123",
        "email": "user@yahoo.com",
        "hd": None,
        "email_verified": True,
    }
    assert google_authoritative(payload) is False


def test_unverified_email_is_never_authoritative_even_for_workspace():
    payload = {
        "sub": "123",
        "email": "user@empresa.com",
        "hd": "empresa",
        "email_verified": False,
    }
    assert google_authoritative(payload) is False


def test_missing_email_is_not_authoritative():
    assert google_authoritative({"sub": "123", "email_verified": True}) is False
