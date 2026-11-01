"""Providers de WhatsApp (RF-P10-07, C7).

Safe mode: cero SDK, cero I/O externo. Dos implementaciones:
- `WaMeProvider`: genera el link `wa.me` (el humano envia); estado
  `sent` fijo, sin `message_id`.
- `MockBusinessApiProvider`: simula el envio directo por Cloud API con
  `message_id` deterministico (hash de phone+message), para probar la
  maquina de estados sin credenciales. El provider real llegara con la
  conexion de UC-03 (Security Handoff).

Incluye normalizacion a E.164 (+54 default para formatos locales AR) y
generacion del link con URL-encoding correcto (es-AR: $, acentos, ñ).
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from urllib.parse import quote_plus

DEFAULT_COUNTRY_CODE = "+54"
_E164_MIN_DIGITS = 8
_E164_MAX_DIGITS = 15
_LOCAL_AR_LENGTHS = (10, 11)


@dataclass(frozen=True)
class WhatsAppSendResult:
    """Resultado de un envio por provider."""

    provider: str
    status: str  # "sent"
    message_id: str | None = None  # solo business_api
    url: str | None = None  # solo wa_me


@runtime_checkable
class WhatsAppProvider(Protocol):
    """Contrato agnostico de envio de WhatsApp (RF-P10-07)."""

    name: str

    async def send(self, phone: str, message: str) -> WhatsAppSendResult:
        """Envia `message` a `phone` (se normaliza a E.164)."""
        ...  # type: ignore[misc]


def normalize_e164(phone: str) -> str:
    """Normaliza un telefono a E.164; +54 default para formato local AR.

    - `+54...` → se valida y se devuelve tal cual.
    - `0054...` → prefijo internacional → `+54...`.
    - 10/11 dígitos (sin `+`) → formato local AR → `+54` + dígitos.
    """
    cleaned = re.sub(r"[\s\-().]+", "", phone.strip())
    if not cleaned:
        raise ValueError("phone requerido")

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    elif cleaned.startswith("00"):
        digits = cleaned[2:]
    elif cleaned.isdigit() and len(cleaned) in _LOCAL_AR_LENGTHS:
        digits = DEFAULT_COUNTRY_CODE[1:] + cleaned
    else:
        digits = cleaned.lstrip("0") if cleaned.isdigit() else cleaned

    if not digits.isdigit() or not (
        _E164_MIN_DIGITS <= len(digits) <= _E164_MAX_DIGITS
    ):
        raise ValueError(f"telefono invalido (no E.164): {phone!r}")
    return f"+{digits}"


def wa_me_url(phone: str, message: str) -> str:
    """Genera `https://wa.me/{E.164 sin +}?text={mensaje URL-encoded}`."""
    e164 = normalize_e164(phone)
    return f"https://wa.me/{e164.lstrip('+')}?text={quote_plus(message)}"


class WaMeProvider:
    """Provider actual: genera el link `wa.me` prellenado (sin I/O)."""

    name = "wa_me"

    async def send(self, phone: str, message: str) -> WhatsAppSendResult:
        url = wa_me_url(phone, message)
        return WhatsAppSendResult(
            provider=self.name, status="sent", message_id=None, url=url
        )


class MockBusinessApiProvider:
    """Mock de Business API (safe mode): message_id deterministico.

    Determinismo: mismo (phone, message) → mismo `message_id`, lo que
    permite testear idempotencia/dedupe sin proveedor real.
    """

    name = "business_api"

    def __init__(self, phone_number_id: str = "MOCK_PHONE_NUMBER_ID"):
        self.phone_number_id = phone_number_id

    async def send(self, phone: str, message: str) -> WhatsAppSendResult:
        e164 = normalize_e164(phone)
        raw = f"{self.phone_number_id}:{e164}:{message}".encode()
        digest = hashlib.sha256(raw).hexdigest()
        return WhatsAppSendResult(
            provider=self.name,
            status="sent",
            message_id=f"MOCK_WA_{digest[:24]}",
            url=None,
        )
