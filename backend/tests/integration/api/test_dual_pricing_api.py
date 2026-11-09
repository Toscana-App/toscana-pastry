
from pg_support import make_test_engine
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from main import app
from data.models import Base
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from domain.models import User, UserRole

SETTINGS_PATH = "/api/v1/tenant/settings"

TORTA_ITEMS = [
    {"qty": "250", "unit": "g", "price_per_purchase_unit": 280000, "purchase_unit": "kg"},
    {"qty": "4", "unit": "unidad", "price_per_purchase_unit": 9000, "purchase_unit": "unidad"},
    {"qty": "1.5", "unit": "l", "price_per_purchase_unit": 120000, "purchase_unit": "l"},
]


def _make_engine():
    return make_test_engine()


def _make_session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _seed(engine, users):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = _make_session_factory(engine)
    async with factory() as session:
        for u in users:
            await SQLUserRepository(session).save(u)


def _override_deps(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_get_user_repository():
        async with session_factory() as session:
            yield SQLUserRepository(session)

    async def override_get_settings_repository():
        async with session_factory() as session:
            yield SQLSettingsRepository(session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository


async def _token_for(ac: AsyncClient, email: str) -> str:
    resp = await ac.post("/api/v1/auth/login", json={"email": email})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _put_settings(ac: AsyncClient, token: str, markup: str = "40") -> None:
    await ac.put(
        SETTINGS_PATH,
        json={
            "hourly_rate": 15000,
            "margin_pct": "100",
            "round_step": 500,
            "include_labor": True,
            "include_gas": False,
            "gas_pct": "0",
            "include_waste": False,
            "waste_pct": "0",
            "urgent_surcharge_pct": "20",
            "consumer_markup_pct": markup,
            "default_prep_minutes": 30,
            "default_servings": 6,
            "default_difficulty": "simple",
        },
        headers={"Authorization": f"Bearer {token}"},
    )




@pytest.mark.asyncio
async def test_admin_gets_both_prices():
    engine = _make_engine()
    factory = _make_session_factory(engine)
    await _seed(engine, [User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN)])
    _override_deps(factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token_for(ac, "admin@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await _put_settings(ac, token, markup="40")

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": "revendedores"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["audience"] == "revendedores"
        assert "rounded" in r.json()

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": "consumidor_final"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["audience"] == "consumidor_final"

    app.dependency_overrides.clear()




@pytest.mark.asyncio
async def test_negocio_only_revendedores():
    engine = _make_engine()
    factory = _make_session_factory(engine)
    await _seed(engine, [User(id="negocio-1", email="negocio@example.com", role=UserRole.NEGOCIO)])
    _override_deps(factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token_for(ac, "negocio@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await _put_settings(ac, token, markup="40")

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": "revendedores"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["audience"] == "revendedores"

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": "consumidor_final"},
            headers=headers,
        )
        assert r.status_code == 403

    app.dependency_overrides.clear()




@pytest.mark.asyncio
async def test_cliente_only_consumer_final():
    engine = _make_engine()
    factory = _make_session_factory(engine)
    await _seed(engine, [User(id="cliente-1", email="cliente@example.com", role=UserRole.CUSTOMER)])
    _override_deps(factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token_for(ac, "cliente@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await _put_settings(ac, token, markup="40")

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": "consumidor_final"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["audience"] == "consumidor_final"

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": "revendedores"},
            headers=headers,
        )
        assert r.status_code == 403

    app.dependency_overrides.clear()




@pytest.mark.asyncio
async def test_markup_configurable_25():
    engine = _make_engine()
    factory = _make_session_factory(engine)
    await _seed(engine, [User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN)])
    _override_deps(factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token_for(ac, "admin@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await _put_settings(ac, token, markup="25")

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": "consumidor_final"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["audience"] == "consumidor_final"
        rounded = Decimal(r.json()["rounded"])
        assert rounded > Decimal("0")

    app.dependency_overrides.clear()




@pytest.mark.asyncio
async def test_exact_numeric_base_x_1_40():
    engine = _make_engine()
    factory = _make_session_factory(engine)
    await _seed(engine, [User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN)])
    _override_deps(factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token_for(ac, "admin@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await _put_settings(ac, token, markup="40")

        r_base = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": "revendedores"},
            headers=headers,
        )
        assert r_base.status_code == 200
        base_rounded = Decimal(r_base.json()["rounded"])

        r_cons = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": "consumidor_final"},
            headers=headers,
        )
        assert r_cons.status_code == 200
        cons_rounded = Decimal(r_cons.json()["rounded"])

        expected = (base_rounded * Decimal("1.40")).quantize(
            Decimal("0.01"), rounding="ROUND_HALF_UP"
        )
        assert cons_rounded == expected

    app.dependency_overrides.clear()




@pytest.mark.asyncio
async def test_role_audience_matrix():
    engine = _make_engine()
    factory = _make_session_factory(engine)
    await _seed(
        engine,
        [
            User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN),
            User(id="negocio-1", email="negocio@example.com", role=UserRole.NEGOCIO),
            User(id="cliente-1", email="cliente@example.com", role=UserRole.CUSTOMER),
        ],
    )
    _override_deps(factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        tok_admin = await _token_for(ac, "admin@example.com")
        tok_negocio = await _token_for(ac, "negocio@example.com")
        tok_cliente = await _token_for(ac, "cliente@example.com")

        await _put_settings(ac, tok_admin, markup="40")

        matrix = [
            ("admin", tok_admin, "revendedores", 200),
            ("admin", tok_admin, "consumidor_final", 200),
            ("negocio", tok_negocio, "revendedores", 200),
            ("negocio", tok_negocio, "consumidor_final", 403),
            ("cliente", tok_cliente, "revendedores", 403),
            ("cliente", tok_cliente, "consumidor_final", 200),
        ]

        for role, tok, audience, expected in matrix:
            r = await ac.post(
                "/api/v1/pricing/preview/dual",
                json={"line_items": TORTA_ITEMS, "prep_minutes": 30, "audience": audience},
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == expected, (
                f"{role} + {audience}: esperado {expected}, obtuvo {r.status_code}"
            )

    app.dependency_overrides.clear()




@pytest.mark.asyncio
async def test_preview_without_audience_param_uses_role_default():
    engine = _make_engine()
    factory = _make_session_factory(engine)
    await _seed(
        engine,
        [
            User(id="negocio-1", email="negocio@example.com", role=UserRole.NEGOCIO),
            User(id="cliente-1", email="cliente@example.com", role=UserRole.CUSTOMER),
        ],
    )
    _override_deps(factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        tok_negocio = await _token_for(ac, "negocio@example.com")
        tok_cliente = await _token_for(ac, "cliente@example.com")

        await _put_settings(ac, tok_negocio, markup="40")

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30},
            headers={"Authorization": f"Bearer {tok_negocio}"},
        )
        assert r.status_code == 200
        assert r.json()["audience"] == "revendedores"

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30},
            headers={"Authorization": f"Bearer {tok_cliente}"},
        )
        assert r.status_code == 200
        assert r.json()["audience"] == "consumidor_final"

    app.dependency_overrides.clear()




@pytest.mark.asyncio
async def test_admin_without_audience_param_defaults_to_revendedores():
    engine = _make_engine()
    factory = _make_session_factory(engine)
    await _seed(engine, [User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN)])
    _override_deps(factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token_for(ac, "admin@example.com")
        await _put_settings(ac, token, markup="40")

        r = await ac.post(
            "/api/v1/pricing/preview/dual",
            json={"line_items": TORTA_ITEMS, "prep_minutes": 30},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["audience"] == "revendedores"

    app.dependency_overrides.clear()
