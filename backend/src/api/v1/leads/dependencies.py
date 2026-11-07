"""Dependencies para leads (RF-P11-13, C5)."""

from data.repositories.sql_lead_repository import SQLLeadRepository


def get_lead_repository() -> SQLLeadRepository:
    """FastAPI dependency: returns SQLLeadRepository bound to the request session."""
    from data.db import get_db

    session = get_db()
    return SQLLeadRepository(session)  # type: ignore[arg-type]
