import sqlite3
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "migrations" / "0012_order_items_drop_qty.sql"


def _portable_section() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index("-- === upgrade (portable) ===")
    end = text.index("-- === upgrade (postgres only) ===")
    return text[start:end].replace("ADD COLUMN IF NOT EXISTS", "ADD COLUMN")


def _create_order_items_0011(conn: sqlite3.Connection) -> None:
    # Estado previo (0011): order_items con la columna redundante qty y la
    # canónica quantity.
    conn.execute(
        """
        CREATE TABLE order_items (
            id VARCHAR PRIMARY KEY,
            order_id VARCHAR NOT NULL,
            product_id VARCHAR NOT NULL,
            product_name VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price VARCHAR,
            portion_note VARCHAR NOT NULL DEFAULT '',
            qty INTEGER,
            portions INTEGER,
            note TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0,
            snapshot TEXT
        )
        """
    )


def test_upgrade_drops_qty_and_preserves_canonical_quantity():
    conn = sqlite3.connect(":memory:")
    _create_order_items_0011(conn)
    # Row divergente: quantity=2 (canónica), qty=3 (redundante).
    conn.execute(
        "INSERT INTO order_items (id, order_id, product_id, product_name, quantity, qty) "
        "VALUES ('i1', 'o1', 'p1', 'Torta', 2, 3)"
    )
    # Row con qty NULL (es nullable): también debe sobrevivir.
    conn.execute(
        "INSERT INTO order_items (id, order_id, product_id, product_name, quantity) "
        "VALUES ('i2', 'o1', 'p2', 'Alfajor', 7)"
    )

    conn.executescript(_portable_section())

    columns = [row[1] for row in conn.execute("PRAGMA table_info(order_items)")]
    assert "qty" not in columns
    assert "quantity" in columns

    # La row divergente queda intacta con la canónica quantity=2.
    row = conn.execute(
        "SELECT id, order_id, product_id, product_name, quantity "
        "FROM order_items WHERE id = 'i1'"
    ).fetchone()
    assert row == ("i1", "o1", "p1", "Torta", 2)

    # La row con qty NULL conserva su quantity.
    (quantity,) = conn.execute(
        "SELECT quantity FROM order_items WHERE id = 'i2'"
    ).fetchone()
    assert quantity == 7


def test_script_drops_qty_and_has_commented_downgrade():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "ALTER TABLE order_items DROP COLUMN qty" in text
    downgrade = text[text.index("-- === downgrade"):]
    assert all(line.startswith("--") for line in downgrade.splitlines() if line.strip())
