
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

    provider: str
    status: str
    message_id: str | None = None
    url: str | None = None


@runtime_checkable
class WhatsAppProvider(Protocol):

    name: str

    async def send(self, phone: str, message: str) -> WhatsAppSendResult:
        ...


def normalize_e164(phone: str) -> str:
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
    e164 = normalize_e164(phone)
    return f"https://wa.me/{e164.lstrip('+')}?text={quote_plus(message)}"


class WaMeProvider:

    name = "wa_me"

    async def send(self, phone: str, message: str) -> WhatsAppSendResult:
        url = wa_me_url(phone, message)
        return WhatsAppSendResult(
            provider=self.name, status="sent", message_id=None, url=url
        )


class MockBusinessApiProvider:

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
