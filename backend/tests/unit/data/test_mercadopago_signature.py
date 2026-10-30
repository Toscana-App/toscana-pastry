"""Mercado Pago webhook signature (S1): HMAC-SHA256 over the official manifest."""

from __future__ import annotations

import hashlib
import hmac

from data.payments.mercadopago import verify_mp_signature

SECRET = "webhook-secret"
DATA_ID = "123456"
REQUEST_ID = "req-abc"
TS = "1704908010"


def _v1(data_id: str = DATA_ID, request_id: str = REQUEST_ID, ts: str = TS) -> str:
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    return hmac.new(SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted() -> None:
    header = f"ts={TS},v1={_v1()}"
    assert verify_mp_signature(SECRET, DATA_ID, REQUEST_ID, header) is True


def test_spaces_around_parts_are_tolerated() -> None:
    header = f"ts={TS}, v1={_v1()}"
    assert verify_mp_signature(SECRET, DATA_ID, REQUEST_ID, header) is True


def test_tampered_v1_is_rejected() -> None:
    header = f"ts={TS},v1={'0' * 64}"
    assert verify_mp_signature(SECRET, DATA_ID, REQUEST_ID, header) is False


def test_tampered_ts_is_rejected() -> None:
    header = f"ts=1704908011,v1={_v1()}"
    assert verify_mp_signature(SECRET, DATA_ID, REQUEST_ID, header) is False


def test_other_data_id_is_rejected() -> None:
    header = f"ts={TS},v1={_v1()}"
    assert verify_mp_signature(SECRET, "999", REQUEST_ID, header) is False


def test_other_request_id_is_rejected() -> None:
    header = f"ts={TS},v1={_v1()}"
    assert verify_mp_signature(SECRET, DATA_ID, "req-other", header) is False


def test_wrong_secret_is_rejected() -> None:
    header = f"ts={TS},v1={_v1()}"
    assert verify_mp_signature("other-secret", DATA_ID, REQUEST_ID, header) is False


def test_missing_or_malformed_header_is_rejected() -> None:
    for header in (None, "", "garbage", f"ts={TS}", f"v1={_v1()}"):
        assert verify_mp_signature(SECRET, DATA_ID, REQUEST_ID, header) is False


def test_non_ascii_v1_is_rejected_not_raised() -> None:
    assert verify_mp_signature(SECRET, DATA_ID, REQUEST_ID, f"ts={TS},v1=\xe9") is False


def test_missing_request_id_or_secret_is_rejected() -> None:
    header = f"ts={TS},v1={_v1()}"
    assert verify_mp_signature(SECRET, DATA_ID, None, header) is False
    assert verify_mp_signature("", DATA_ID, REQUEST_ID, header) is False
