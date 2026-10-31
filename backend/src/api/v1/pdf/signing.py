"""Tokens firmados para el link temporal del PDF (P9).

token = base64url(payload) + "." + base64url(HMAC-SHA256(payload, key))
payload = "v1|<budget_id>|<expires_unix>"
key     = HMAC-SHA256(SECRET_KEY, b"pdf-share-v1")  (separación de dominio)

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

# Separación de dominio + versión del formato del payload.
_KEY_CONTEXT = b"pdf-share-v1"
_PAYLOAD_VERSION = "v1"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _signing_key(secret: str) -> bytes:
    """Subclave con separación de dominio: la SECRET_KEY (compartida con
    el JWT) nunca firma directamente los links del PDF."""
    return hmac.new(
        secret.encode("utf-8"), _KEY_CONTEXT, hashlib.sha256
    ).digest()


def make_share_token(
    budget_id: str, secret: str, ttl_seconds: int = TTL_SECONDS
) -> Tuple[str, int]:
    """(token, expires_unix). ttl_seconds <= 0 → token ya vencido
    (útil para tests de expiración)."""
    expires = int(time.time()) + ttl_seconds
    payload = f"{_PAYLOAD_VERSION}|{budget_id}|{expires}".encode("utf-8")
    sig = hmac.new(_signing_key(secret), payload, hashlib.sha256).digest()
    return f"{_b64encode(payload)}.{_b64encode(sig)}", expires


def verify_share_token(token: str, secret: str) -> Optional[str]:
    """El budget_id si el token es válido; None si está mal firmado,
    alterado o vencido (misma respuesta: no se revela el motivo)."""
    try:
        payload_part, sig_part = token.split(".", 1)
        payload = _b64decode(payload_part)
        expected = hmac.new(
            _signing_key(secret), payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(sig_part)):
            return None
        version, budget_id, expires = payload.decode("utf-8").split("|")
        if version != _PAYLOAD_VERSION:
            return None
        if int(expires) < time.time():
            return None
        return budget_id
    except Exception:
        return None
