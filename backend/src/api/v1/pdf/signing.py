"""Tokens firmados para el link temporal del PDF (P9).

token = base64url(payload) + "." + base64url(HMAC-SHA256(payload, SECRET_KEY))
payload = "<budget_id>|<expires_unix>"

Sin estado (no se guarda nada en DB): la firma se verifica en cada
acceso. TTL 72 h (P9: link temporal de 72 h). Sin PII en el token ni
en los logs: solo el id del presupuesto (RNF-P10-05, criterio extendido).
"""
import base64
import hashlib
import hmac
import time
from typing import Optional, Tuple

# P9: link temporal de 72 horas.
TTL_SECONDS = 72 * 3600


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def make_share_token(
    budget_id: str, secret: str, ttl_seconds: int = TTL_SECONDS
) -> Tuple[str, int]:
    """(token, expires_unix). ttl_seconds <= 0 → token ya vencido
    (útil para tests de expiración)."""
    expires = int(time.time()) + ttl_seconds
    payload = f"{budget_id}|{expires}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{_b64encode(payload)}.{_b64encode(sig)}", expires


def verify_share_token(token: str, secret: str) -> Optional[str]:
    """El budget_id si el token es válido; None si está mal firmado,
    alterado o vencido (misma respuesta: no se revela el motivo)."""
    try:
        payload_part, sig_part = token.split(".", 1)
        payload = _b64decode(payload_part)
        expected = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(sig_part)):
            return None
        budget_id, expires = payload.decode("utf-8").split("|")
        if int(expires) < time.time():
            return None
        return budget_id
    except Exception:
        return None
