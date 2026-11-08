
from data.repositories.sql_lead_repository import SQLLeadRepository


def get_lead_repository() -> SQLLeadRepository:
    from data.db import get_db

    session = get_db()
    return SQLLeadRepository(session)
