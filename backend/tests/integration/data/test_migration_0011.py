import re
import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError

from data.models import Base, CustomerORM, OrderORM

SCRIPT = Path(__file__).resolve().parents[3] / "migrations" / "0011_orders_customer_fk.sql"


def _upgrade_section() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    return text[text.index("-- Upgrade"): text.index("-- Downgrade")]


def _schema_engine():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = (CustomerORM.__table__, OrderORM.__table__)
    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=tables)
    return engine


def _customer_row(customer_id: str) -> dict:
    return {
        "id": customer_id,
        "name": "Ana",
        "phone": "11-1111-1111",
        "name_norm": "ana",
        "phone_norm": "11111111",
        "created_at": datetime.datetime.now(datetime.UTC),
    }


def _order_row(order_id: str, customer_id: str) -> dict:
    return {
        "id": order_id,
        "customer_id": customer_id,
        "code": f"ORD-{order_id}",
        "status": "nuevo",
        "date": datetime.datetime.now(datetime.UTC),
        "created_at": datetime.datetime.now(datetime.UTC),
    }


def test_upgrade_adds_named_foreign_key_to_customers():
    assert re.search(
        r"ALTER TABLE orders\s+ADD CONSTRAINT fk_orders_customer_id\s+"
        r"FOREIGN KEY \(customer_id\) REFERENCES customers \(id\)",
        _upgrade_section(),
    )


def test_downgrade_is_commented_out():
    text = SCRIPT.read_text(encoding="utf-8")
    downgrade = text[text.index("-- Downgrade"):]
    assert all(line.startswith("--") for line in downgrade.splitlines() if line.strip())


def test_order_with_existing_customer_commits():
    engine = _schema_engine()
    try:
        with engine.begin() as connection:
            connection.execute(CustomerORM.__table__.insert(), _customer_row("c1"))
            connection.execute(OrderORM.__table__.insert(), _order_row("o1", "c1"))
    finally:
        engine.dispose()


def test_order_with_dangling_customer_id_raises_integrity_error():
    engine = _schema_engine()
    try:
        with engine.begin() as connection:
            connection.execute(CustomerORM.__table__.insert(), _customer_row("c1"))
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    OrderORM.__table__.insert(), _order_row("o2", "missing-customer")
                )
    finally:
        engine.dispose()
