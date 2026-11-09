
from data.repositories.sql_whatsapp_send_repository import (
    SQLWhatsAppSendRepository,
)
from domain.whatsapp_provider import MockBusinessApiProvider, WhatsAppProvider


def get_whatsapp_send_repository() -> SQLWhatsAppSendRepository:
    from data.db import get_db

    session = get_db()
    return SQLWhatsAppSendRepository(session)


def get_whatsapp_provider() -> WhatsAppProvider:
    return MockBusinessApiProvider()
