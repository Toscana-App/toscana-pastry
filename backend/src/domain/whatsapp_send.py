
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Literal

SendStatus = Literal["sent", "delivered", "read", "failed"]
SendProvider = Literal["wa_me", "business_api"]

ALLOWED_STATUSES = ("sent", "delivered", "read", "failed")
ALLOWED_PROVIDERS = ("wa_me", "business_api")
STATUS_PRIORITY = {"sent": 1, "delivered": 2, "read": 3}

BUSINESS_API_DAILY_LIMIT = 500


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _strip(value: str) -> str:
    return value.strip()


@dataclass(frozen=True)
class WhatsAppSend:

    provider: SendProvider
    phone: str
    message: str
    reference_kind: str
    reference_id: str
    sent_at: datetime
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: SendStatus = "sent"
    message_id: str | None = None
    failed_reason: str | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None

    def __post_init__(self):
        object.__setattr__(self, "phone", _strip(self.phone))
        object.__setattr__(self, "message", _strip(self.message))
        object.__setattr__(self, "reference_id", _strip(self.reference_id))

        if self.provider not in ALLOWED_PROVIDERS:
            raise ValueError(
                f"provider invalido: {self.provider!r} (permitido: {ALLOWED_PROVIDERS})"
            )
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(
                f"status invalido: {self.status!r} (permitido: {ALLOWED_STATUSES})"
            )
        if not self.phone:
            raise ValueError("phone requerido y no puede ser solo espacios")
        if not self.message:
            raise ValueError("message requerido y no puede ser solo espacios")
        if not self.reference_id:
            raise ValueError("reference_id requerido y no puede ser solo espacios")


def apply_status(
    send: WhatsAppSend,
    new_status: SendStatus,
    *,
    failed_reason: str | None = None,
    now: datetime | None = None,
) -> WhatsAppSend:
    if new_status not in ALLOWED_STATUSES:
        raise ValueError(
            f"status invalido: {new_status!r} (permitido: {ALLOWED_STATUSES})"
        )
    if send.status == "failed" and new_status != "failed":
        return send
    if new_status == send.status:
        return send

    timestamp = now or _utcnow()

    if new_status == "failed":
        return replace(send, status="failed", failed_reason=failed_reason)

    if STATUS_PRIORITY[new_status] < STATUS_PRIORITY[send.status]:
        return send

    updated = replace(send, status=new_status)
    if new_status == "delivered":
        updated = replace(updated, delivered_at=timestamp)
    elif new_status == "read":
        updated = replace(
            updated,
            read_at=timestamp,
            delivered_at=send.delivered_at or timestamp,
        )
    return updated


def can_resend(send: WhatsAppSend) -> bool:
    return send.status == "failed" and send.provider == "business_api"


def reset_for_resend(
    send: WhatsAppSend, *, new_message_id: str, now: datetime | None = None
) -> WhatsAppSend:
    if not can_resend(send):
        raise ValueError("el envio no es reintenable (solo failed + business_api)")
    return replace(
        send,
        status="sent",
        failed_reason=None,
        delivered_at=None,
        read_at=None,
        message_id=new_message_id,
        sent_at=now or _utcnow(),
    )


def read_rate(total: int, read: int) -> float:
    if total <= 0:
        return 0.0
    return read / total
