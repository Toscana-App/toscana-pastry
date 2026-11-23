import datetime
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from api.v1.dependencies import set_rls_context, set_rls_webhook_order
from pg_support import URL

RLS_ROLE = "toscana_app"
RLS_PASSWORD = "toscana_app_password"
MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "migrations" / "0018_rls_role_policies.sql"
)
OWNED_TABLES = (
    "cart",
    "cart_items",
    "customer_addresses",
    "orders",
    "order_items",
    "order_events",
    "order_idempotency_keys",
)


def _conn_args(user: str, password: str) -> dict:
    return {
        "user": user,
        "password": password,
        "host": URL.host,
        "port": URL.port,
        "database": URL.database,
    }


async def _admin_connect() -> asyncpg.Connection:
    return await asyncpg.connect(**_conn_args(URL.username, URL.password))


async def _app_connect() -> asyncpg.Connection:
    return await asyncpg.connect(**_conn_args(RLS_ROLE, RLS_PASSWORD))


async def _apply_rls(admin: asyncpg.Connection) -> None:
    policies = await admin.fetch(
        "SELECT policyname, tablename FROM pg_policies WHERE schemaname = 'public'"
    )
    for row in policies:
        await admin.execute(
            f'DROP POLICY IF EXISTS "{row["policyname"]}" ON public."{row["tablename"]}"'
        )
    upgrade = MIGRATION_PATH.read_text().split("-- Downgrade")[0]
    upgrade = upgrade.replace(
        "ON DATABASE toscana_db", f'ON DATABASE "{URL.database}"'
    )
    await admin.execute(upgrade)


async def _seed(admin: asyncpg.Connection) -> dict:
    now = datetime.datetime.now(datetime.UTC)
    suffix = uuid.uuid4().hex[:8]
    user_a = f"user-a-{suffix}"
    user_b = f"user-b-{suffix}"
    order_a = f"order-a-{suffix}"
    order_b = f"order-b-{suffix}"
    address_a = f"address-a-{suffix}"
    address_b = f"address-b-{suffix}"
    await admin.execute(
        "INSERT INTO users (id, email, role) VALUES ($1, $2, 'customer'), ($3, $4, 'customer')",
        user_a,
        f"{user_a}@test.local",
        user_b,
        f"{user_b}@test.local",
    )
    await admin.execute(
        "INSERT INTO cart (user_id, updated_at) VALUES ($1, $2), ($3, $2)",
        user_a,
        now,
        user_b,
    )
    await admin.execute(
        "INSERT INTO cart_items (user_id, product_id, qty, created_at)"
        " VALUES ($1, 'prod-1', 1, $2), ($3, 'prod-1', 2, $2)",
        user_a,
        now,
        user_b,
    )
    await admin.execute(
        "INSERT INTO customer_addresses (id, user_id, street_line_1, is_default, created_at, updated_at)"
        " VALUES ($1, $2, 'Calle A 1', false, $4, $4), ($3, $5, 'Calle B 1', false, $4, $4)",
        address_a,
        user_a,
        address_b,
        now,
        user_b,
    )
    for order_id, customer_id, code in (
        (order_a, user_a, f"#RA{suffix[:4]}"),
        (order_b, user_b, f"#RB{suffix[:4]}"),
    ):
        await admin.execute(
            "INSERT INTO orders (id, customer_id, code, status, date, payment_method,"
            " delivery_mode, delivery_address, created_at)"
            " VALUES ($1, $2, $3, 'nuevo', $4, 'cash', 'delivery', '', $4)",
            order_id,
            customer_id,
            code,
            now,
        )
        await admin.execute(
            "INSERT INTO order_items (id, order_id, product_id, product_name, quantity,"
            " portion_note, note, position)"
            " VALUES ($1, $2, 'prod-1', 'Torta', 1, '', '', 0)",
            f"item-{order_id}",
            order_id,
        )
        await admin.execute(
            "INSERT INTO order_events (id, order_id, type, payload, created_at)"
            " VALUES ($1, $2, 'created', '', $3)",
            f"event-{order_id}",
            order_id,
            now,
        )
        await admin.execute(
            "INSERT INTO order_idempotency_keys (id, user_id, key, body_hash, order_id, expires_at)"
            " VALUES ($1, $2, $3, 'hash', $4, $5)",
            f"{customer_id}:{order_id}",
            customer_id,
            order_id,
            order_id,
            now + datetime.timedelta(hours=24),
        )
    return {
        "user_a": user_a,
        "user_b": user_b,
        "order_a": order_a,
        "order_b": order_b,
    }


async def _set_ctx(
    conn: asyncpg.Connection,
    role: str = "",
    user_id: str = "",
    order_id: str = "",
) -> None:
    await conn.execute(
        "SELECT set_config('app.current_user_id', $1, false),"
        " set_config('app.current_role', $2, false),"
        " set_config('app.webhook_order_id', $3, false)",
        user_id,
        role,
        order_id,
    )


async def _count(conn: asyncpg.Connection, table: str) -> int:
    return await conn.fetchval(f'SELECT count(*) FROM public."{table}"')


async def _cleanup(admin: asyncpg.Connection, ids: dict) -> None:
    order_ids = [ids["order_a"], ids["order_b"]]
    user_ids = [ids["user_a"], ids["user_b"]]
    await admin.execute(
        "DELETE FROM order_events WHERE order_id = ANY($1::text[])", order_ids
    )
    await admin.execute(
        "DELETE FROM order_items WHERE order_id = ANY($1::text[])", order_ids
    )
    await admin.execute(
        "DELETE FROM order_idempotency_keys WHERE user_id = ANY($1::text[])", user_ids
    )
    await admin.execute("DELETE FROM orders WHERE id = ANY($1::text[])", order_ids)
    await admin.execute(
        "DELETE FROM cart_items WHERE user_id = ANY($1::text[])", user_ids
    )
    await admin.execute("DELETE FROM cart WHERE user_id = ANY($1::text[])", user_ids)
    await admin.execute(
        "DELETE FROM customer_addresses WHERE user_id = ANY($1::text[])", user_ids
    )
    await admin.execute("DELETE FROM users WHERE id = ANY($1::text[])", user_ids)


@pytest_asyncio.fixture
async def rls_seed():
    admin = await _admin_connect()
    try:
        await _apply_rls(admin)
        ids = await _seed(admin)
        yield ids
        await _cleanup(admin, ids)
    finally:
        await admin.close()


class TestRlsRolePolicies:
    async def test_customer_sees_only_own_rows(self, rls_seed):
        conn = await _app_connect()
        try:
            await _set_ctx(conn, role="customer", user_id=rls_seed["user_a"])
            for table in OWNED_TABLES:
                assert await _count(conn, table) == 1, table
            order_id = await conn.fetchval("SELECT id FROM orders")
            assert order_id == rls_seed["order_a"]
        finally:
            await conn.close()

    async def test_customer_cannot_read_other_order(self, rls_seed):
        conn = await _app_connect()
        try:
            await _set_ctx(conn, role="customer", user_id=rls_seed["user_a"])
            row = await conn.fetchrow(
                "SELECT id FROM orders WHERE id = $1", rls_seed["order_b"]
            )
            assert row is None
        finally:
            await conn.close()

    async def test_anonymous_sees_nothing(self, rls_seed):
        conn = await _app_connect()
        try:
            for table in OWNED_TABLES:
                assert await _count(conn, table) == 0, table
        finally:
            await conn.close()

    async def test_admin_sees_all_rows(self, rls_seed):
        conn = await _app_connect()
        try:
            await _set_ctx(conn, role="admin")
            assert await _count(conn, "orders") == 2
            assert await _count(conn, "cart") == 2
            assert await _count(conn, "customer_addresses") == 2
        finally:
            await conn.close()

    async def test_negocio_is_scoped_like_customer(self, rls_seed):
        conn = await _app_connect()
        try:
            await _set_ctx(conn, role="negocio", user_id=rls_seed["user_a"])
            assert await _count(conn, "orders") == 1
            order_id = await conn.fetchval("SELECT id FROM orders")
            assert order_id == rls_seed["order_a"]
        finally:
            await conn.close()

    async def test_webhook_context_limits_to_one_order(self, rls_seed):
        conn = await _app_connect()
        try:
            await _set_ctx(conn, order_id=rls_seed["order_b"])
            assert await _count(conn, "orders") == 1
            assert await _count(conn, "order_items") == 1
            order_id = await conn.fetchval("SELECT id FROM orders")
            assert order_id == rls_seed["order_b"]
        finally:
            await conn.close()

    async def test_customer_insert_foreign_order_is_denied(self, rls_seed):
        conn = await _app_connect()
        try:
            await _set_ctx(conn, role="customer", user_id=rls_seed["user_a"])
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await conn.execute(
                    "INSERT INTO orders (id, customer_id, code, status, date,"
                    " payment_method, delivery_mode, delivery_address, created_at)"
                    " VALUES ('intruder', $1, '#INTR', 'nuevo', now(), 'cash',"
                    " 'delivery', '', now())",
                    rls_seed["user_b"],
                )
        finally:
            await conn.close()

    async def test_customer_update_foreign_order_affects_no_rows(self, rls_seed):
        conn = await _app_connect()
        try:
            await _set_ctx(conn, role="customer", user_id=rls_seed["user_a"])
            status = await conn.execute(
                "UPDATE orders SET status = 'confirmado' WHERE id = $1",
                rls_seed["order_b"],
            )
            assert status == "UPDATE 0"
        finally:
            await conn.close()


class _FakeDialect:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeBind:
    def __init__(self, name: str) -> None:
        self.dialect = _FakeDialect(name)


class _FakeSession:
    def __init__(self, dialect: str = "postgresql") -> None:
        self.bind = _FakeBind(dialect)
        self.calls: list[tuple[str, dict | None]] = []

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params))


class _FakeUser:
    def __init__(self, user_id: str, role) -> None:
        self.id = user_id
        self.role = role


class TestRlsContextPlumbing:
    async def test_set_rls_context_sets_user_and_role(self):
        from domain.models import UserRole

        db = _FakeSession()
        await set_rls_context(db, _FakeUser("user-1", UserRole.CUSTOMER))
        statement, params = db.calls[0]
        assert "app.current_user_id" in statement
        assert "app.current_role" in statement
        assert params == {"user_id": "user-1", "role": "customer"}

    async def test_set_rls_webhook_order_sets_order_guc(self):
        db = _FakeSession()
        await set_rls_webhook_order(db, "order-9")
        statement, params = db.calls[0]
        assert "app.webhook_order_id" in statement
        assert params == {"order_id": "order-9"}

    async def test_context_is_skipped_outside_postgresql(self):
        from domain.models import UserRole

        db = _FakeSession(dialect="sqlite")
        await set_rls_context(db, _FakeUser("user-1", UserRole.ADMIN))
        await set_rls_webhook_order(db, "order-9")
        assert db.calls == []
