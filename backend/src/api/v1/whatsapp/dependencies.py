"""Dependencies para el modulo de WhatsApp Business (RF-P10-07/08, C7)."""

from data.repositories.sql_whatsapp_send_repository import (
    SQLWhatsAppSendRepository,
)
from domain.whatsapp_provider import MockBusinessApiProvider, WhatsAppProvider


def get_whatsapp_send_repository() -> SQLWhatsAppSendRepository:
    """FastAPI dependency: SQLWhatsAppSendRepository sobre la session del request."""
    from data.db import get_db

    session = get_db()
    return SQLWhatsAppSendRepository(session)  # type: ignore[arg-type]


def get_whatsapp_provider() -> WhatsAppProvider:
    """Safe mode: sin conexion Cloud API real todavia (UC-03 pendiente).

    El provider real (Business API) se inyecta aqui cuando exista la
    conexion del tenant (Security Handoff de la skill MP).
    """
    return MockBusinessApiProvider()
