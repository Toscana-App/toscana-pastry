"""Integration tests for POST /calc/products/recalculate-all (RF-P3CC-03).

Covers: only active products recalculated in a single transaction,
`last_recalculated_at` set on all actives even when the price does not
change, versions created ONLY when the rounded final differs and
continuing each product's append-only sequence, snapshots re-resolved
from current materials (D4: incomplete -> 0.00 without error),
draft/archived/deleted untouched, 0 active -> {recalculated: 0}, and
auth (401/403, D2).
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.calc.dependencies import (
    get_calc_material_category_repository,
    get_calc_material_repository,
    get_calc_product_category_repository,
    get_calc_product_repository,
    get_calc_settings_repository,
    get_calc_supplier_repository,
)
from data.db import get_db
from data.repositories.calc.sql_calc_material_category_repository import (
    SQLCalcMaterialCategoryRepository,
)
from data.repositories.calc.sql_calc_material_repository import (
    SQLCalcMaterialRepository,
)
from data.repositories.calc.sql_calc_product_category_repository import (
    SQLCalcProductCategoryRepository,
)
from data.repositories.calc.sql_calc_product_repository import (
    SQLCalcProductRepository,
)
from data.repositories.calc.sql_calc_settings_repository import (
    SQLCalcSettingsRepository,
)
from data.repositories.calc.sql_calc_supplier_repository import (
    SQLCalcSupplierRepository,
)
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from main import app

# ─── Fixtures ───────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_calc_settings_repository():
        yield SQLCalcSettingsRepository(db_session)

    async def override_get_material_category_repo():
        yield SQLCalcMaterialCategoryRepository(db_session)

    async def override_get_product_category_repo():
        yield SQLCalcProductCategoryRepository(db_session)

    async def override_get_supplier_repo():
        yield SQLCalcSupplierRepository(db_session)

    async def override_get_material_repo():
        yield SQLCalcMaterialRepository(db_session)

    async def override_get_product_repo():
        yield SQLCalcProductRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_calc_settings_repository] = (
        override_get_calc_settings_repository
    )
    app.dependency_overrides[get_calc_material_category_repository] = (
        override_get_material_category_repo
    )
    app.dependency_overrides[get_calc_product_category_repository] = (
        override_get_product_category_repo
    )
    app.dependency_overrides[get_calc_supplier_repository] = override_get_supplier_repo
    app.dependency_overrides[get_calc_material_repository] = override_get_material_repo
    app.dependency_overrides[get_calc_product_repository] = override_get_product_repo

    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    await SQLUserRepository(db_session).save(
        User(email="customer@example.com", role=UserRole.CUSTOMER)
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


# ─── Helpers ────────────────────────────────────────────────────────────


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.cookies["auth_token"]


async def _admin(client: AsyncClient) -> str:
    return await _token_for(client, "admin@example.com")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_material(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {"name": "Mantequilla"}
    payload.update(overrides)
    response = await client.post(
        "/api/v1/calc/materials", json=payload, headers=_auth(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_product(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {"name": "Brownie"}
    payload.update(overrides)
    response = await client.post(
        "/api/v1/calc/products", json=payload, headers=_auth(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _recalculate_all(client: AsyncClient, token: str) -> dict:
    response = await client.post(
        "/api/v1/calc/products/recalculate-all", headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _seed_full(client: AsyncClient, token: str) -> dict:
    """Material a 100.00 + 3 activos (qty 1) + 1 draft + 1 archived +
    1 eliminado, todos con una linea del material."""
    material = await _create_material(
        client, token, name="Mantequilla",
        unit_of_measure="kg",
        purchase_total_price=10000, package_quantity="1",
    )
    assert material["unit_cost"] == 10000
    lines = [{"material_id": material["id"], "quantity_used": "1"}]
    alpha = await _create_product(
        client, token, name="Alpha", status="active", materials=lines
    )
    beta = await _create_product(
        client, token, name="Beta", status="active", materials=lines
    )
    gamma = await _create_product(
        client, token, name="Gamma", status="active", materials=lines
    )
    delta = await _create_product(
        client, token, name="Delta", status="draft", materials=lines
    )
    epsilon = await _create_product(
        client, token, name="Epsilon", status="archived", materials=lines
    )
    zeta = await _create_product(
        client, token, name="Zeta", status="active", materials=lines
    )
    await client.delete(
        f"/api/v1/calc/products/{zeta['product']['id']}", headers=_auth(token)
    )
    return {
        "material": material,
        "alpha": alpha["product"]["id"],
        "beta": beta["product"]["id"],
        "gamma": gamma["product"]["id"],
        "delta": delta["product"]["id"],
        "epsilon": epsilon["product"]["id"],
        "zeta": zeta["product"]["id"],
    }


async def _detail(client: AsyncClient, token: str, product_id: str) -> dict:
    response = await client.get(
        f"/api/v1/calc/products/{product_id}", headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _versions_total(client: AsyncClient, token: str, product_id: str) -> int:
    response = await client.get(
        f"/api/v1/calc/products/{product_id}/versions", headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    return response.json()["total"]


# ─── Auth (S3/D2: 401 sin sesion, 403 no-admin en writes) ──────────────


class TestRecalculateAllAuth:
    async def test_without_session_returns_401(self, client):
        response = await client.post("/api/v1/calc/products/recalculate-all")
        assert response.status_code == 401

    async def test_as_customer_returns_403(self, client):
        token = await _token_for(client, "customer@example.com")
        response = await client.post(
            "/api/v1/calc/products/recalculate-all", headers=_auth(token)
        )
        assert response.status_code == 403


# ─── Recalculate-all (RF-P3CC-03) ──────────────────────────────────────


class TestRecalculateAll:
    async def test_counts_only_active_products(self, client):
        """3 activos + 1 draft + 1 archived + 1 eliminado -> {recalculated: 3}."""
        token = await _admin(client)
        await _seed_full(client, token)
        assert await _recalculate_all(client, token) == {"recalculated": 3}

    async def test_no_active_products_returns_zero_without_error(self, client):
        token = await _admin(client)
        await _create_product(client, token, name="SoloDraft")
        assert await _recalculate_all(client, token) == {"recalculated": 0}

    async def test_sets_last_recalculated_on_all_actives_without_version(
        self, client
    ):
        """last_recalculated_at se setea en TODOS los activos, aunque el
        precio no cambie; sin cambio de final NO hay versiones."""
        token = await _admin(client)
        seed = await _seed_full(client, token)
        await _recalculate_all(client, token)
        for key in ("alpha", "beta", "gamma"):
            detail = await _detail(client, token, seed[key])
            assert detail["product"]["last_recalculated_at"] is not None
            assert await _versions_total(client, token, seed[key]) == 0

    async def test_draft_archived_and_deleted_untouched(self, client):
        """Drafts/archived/eliminados: lineas, last_recalculated_at y
        versiones sin cambios, aunque el material cambie de precio."""
        token = await _admin(client)
        seed = await _seed_full(client, token)
        await client.patch(
            f"/api/v1/calc/materials/{seed['material']['id']}",
            json={"purchase_total_price": 20000, "package_quantity": "1"},
            headers=_auth(token),
        )
        await _recalculate_all(client, token)
        for key in ("delta", "epsilon"):
            detail = await _detail(client, token, seed[key])
            assert detail["product"]["last_recalculated_at"] is None
            line = detail["materials"][0]
            assert line["unit_cost_snapshot"] == 10000
            assert line["line_total_cost"] == 10000
            assert await _versions_total(client, token, seed[key]) == 0
        # El eliminado ni siquiera es visible.
        response = await client.get(
            f"/api/v1/calc/products/{seed['zeta']}", headers=_auth(token)
        )
        assert response.status_code == 404

    async def test_re_resolves_snapshots_and_versions_only_on_final_change(
        self, client
    ):
        """Snapshots re-resueltos desde el material actual; version solo
        cuando el final redondeado difiere (aqui: todos los 3 activos)."""
        token = await _admin(client)
        seed = await _seed_full(client, token)
        await client.patch(
            f"/api/v1/calc/materials/{seed['material']['id']}",
            json={"purchase_total_price": 20000, "package_quantity": "1"},
            headers=_auth(token),
        )
        await _recalculate_all(client, token)
        for key in ("alpha", "beta", "gamma"):
            detail = await _detail(client, token, seed[key])
            line = detail["materials"][0]
            assert line["unit_cost_snapshot"] == 20000
            assert line["line_total_cost"] == 20000
            # cost 200.00, margin 30 / discount 0 / tax 19:
            # pbd 285.71, profit 85.71, tax 54.28, final 339.99.
            assert detail["costs"]["product_total_cost"] == 20000
            assert detail["costs"]["final_sale_price"] == 33999
            response = await client.get(
                f"/api/v1/calc/products/{seed[key]}/versions",
                headers=_auth(token),
            )
            versions = response.json()
            assert versions["total"] == 1
            assert versions["items"][0]["version_number"] == 1
            assert versions["items"][0]["final_sale_price"] == 33999

    async def test_version_number_continues_product_sequence(self, client):
        """Si un producto ya tenia versiones de recalcules individuales,
        el recalculate-all continua la secuencia (max + 1 por producto)."""
        token = await _admin(client)
        seed = await _seed_full(client, token)

        async def bump(price: int):
            await client.patch(
                f"/api/v1/calc/materials/{seed['material']['id']}",
                json={"purchase_total_price": price, "package_quantity": "1"},
                headers=_auth(token),
            )

        await bump(20000)
        await _recalculate_all(client, token)  # alpha/beta/gamma -> version 1
        assert await _versions_total(client, token, seed["alpha"]) == 1

        await bump(30000)
        response = await client.post(
            f"/api/v1/calc/products/{seed['alpha']}/recalculate",
            headers=_auth(token),
        )
        assert response.status_code == 200
        assert await _versions_total(client, token, seed["alpha"]) == 2

        await bump(40000)
        await _recalculate_all(client, token)
        assert await _versions_total(client, token, seed["alpha"]) == 3
        assert await _versions_total(client, token, seed["beta"]) == 2
        assert await _versions_total(client, token, seed["gamma"]) == 2
        response = await client.get(
            f"/api/v1/calc/products/{seed['alpha']}/versions",
            headers=_auth(token),
        )
        latest = response.json()["items"][0]
        assert latest["version_number"] == 3

    async def test_incomplete_material_snapshots_zero_without_error(self, client):
        """D4: material incomplete (unit_cost None) -> snapshot 0.00,
        sin error; el recalculate-all sigue funcionando y no crea
        version si el final no cambio."""
        token = await _admin(client)
        incomplete = await _create_material(client, token, name="Harina")
        assert incomplete["unit_cost"] is None
        priced = await _create_material(
            client, token, name="Azucar",
            purchase_total_price=5000, package_quantity="1",
        )
        p1 = await _create_product(
            client,
            token,
            name="ConIncompleto",
            status="active",
            materials=[{"material_id": incomplete["id"], "quantity_used": "2"}],
        )
        p2 = await _create_product(
            client,
            token,
            name="ConPreciado",
            status="active",
            materials=[{"material_id": priced["id"], "quantity_used": "1"}],
        )
        # El incomplete sigue a 0.00: su producto no cambia de final.
        await client.patch(
            f"/api/v1/calc/materials/{priced['id']}",
            json={"purchase_total_price": 6000, "package_quantity": "1"},
            headers=_auth(token),
        )
        await _recalculate_all(client, token)
        detail = await _detail(client, token, p1["product"]["id"])
        line = detail["materials"][0]
        assert line["unit_cost_snapshot"] == 0
        assert line["line_total_cost"] == 0
        assert detail["product"]["last_recalculated_at"] is not None
        assert await _versions_total(client, token, p1["product"]["id"]) == 0
        # El otro si cambio: version 1 con el nuevo costo.
        assert await _versions_total(client, token, p2["product"]["id"]) == 1
