import sqlite3
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[3] / "migrations" / "0020_orders_status_english.sql"
)

EXPECTED_MAP = {
    "nuevo": "new",
    "confirmado": "confirmed",
    "entregado": "delivered",
    "cancelado": "cancelled",
}


def _portable_section() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index("-- === upgrade (portable) ===")
    end = text.index("-- === downgrade")
    return text[start:end]


def _create_orders(conn: sqlite3.Connection) -> None:
    # Columnas minimas: el upgrade solo toca `status`.
    conn.execute(
        """
        CREATE TABLE orders (
            id VARCHAR PRIMARY KEY,
            status VARCHAR(20) NOT NULL
        )
        """
    )


def test_upgrade_maps_legacy_spanish_statuses_to_english():
    conn = sqlite3.connect(":memory:")
    _create_orders(conn)
    for i, spanish in enumerate(EXPECTED_MAP, start=1):
        conn.execute(
            "INSERT INTO orders (id, status) VALUES (?, ?)", (f"o{i}", spanish)
        )
    # Filas que ya estan en inglés (post-cutover) no se tocan.
    for i, english in enumerate(("preparing", "pending_delivery", "delivered"), start=10):
        conn.execute(
            "INSERT INTO orders (id, status) VALUES (?, ?)", (f"o{i}", english)
        )

    conn.executescript(_portable_section())

    rows = dict(conn.execute("SELECT id, status FROM orders").fetchall())
    assert rows["o1"] == "new"
    assert rows["o2"] == "confirmed"
    assert rows["o3"] == "delivered"
    assert rows["o4"] == "cancelled"
    assert rows["o10"] == "preparing"
    assert rows["o11"] == "pending_delivery"
    assert rows["o12"] == "delivered"


def test_upgrade_is_idempotent():
    conn = sqlite3.connect(":memory:")
    _create_orders(conn)
    for i, spanish in enumerate(EXPECTED_MAP, start=1):
        conn.execute(
            "INSERT INTO orders (id, status) VALUES (?, ?)", (f"o{i}", spanish)
        )

    portable = _portable_section()
    conn.executescript(portable)
    conn.executescript(portable)

    rows = dict(conn.execute("SELECT id, status FROM orders").fetchall())
    assert all(rows[f"o{i}"] == EXPECTED_MAP[sp] for i, sp in enumerate(EXPECTED_MAP, start=1))


def test_downgrade_is_commented_out():
    text = SCRIPT.read_text(encoding="utf-8")
    downgrade = text[text.index("-- === downgrade"):]
    assert all(
        line.startswith("--") for line in downgrade.splitlines() if line.strip()
    )
