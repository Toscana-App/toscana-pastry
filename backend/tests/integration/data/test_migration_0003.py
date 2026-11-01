"""Upgrade test for migrations/0003: runs the portable section on a prior schema."""
import re
import sqlite3
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "migrations" / "0003_consumer_markup_and_text_roles.sql"


def _portable_section() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index("-- === upgrade (portable) ===")
    end = text.index("-- === upgrade (postgres only) ===")
    return text[start:end].replace("ADD COLUMN IF NOT EXISTS", "ADD COLUMN")


def test_upgrade_adds_consumer_markup_with_default_on_existing_rows():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE business_settings (id INTEGER PRIMARY KEY, hourly_rate VARCHAR NOT NULL)")
    conn.execute("INSERT INTO business_settings (hourly_rate) VALUES ('10')")

    conn.executescript(_portable_section())

    assert conn.execute("SELECT consumer_markup_pct FROM business_settings").fetchone() == ("40",)


def test_script_has_postgres_role_conversion_and_commented_downgrade():
    text = SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"USING lower\(role::text\)", text)
    assert "DROP TYPE" in text
    downgrade = text[text.index("-- === downgrade"):]
    assert all(line.startswith("--") for line in downgrade.splitlines() if line.strip())
