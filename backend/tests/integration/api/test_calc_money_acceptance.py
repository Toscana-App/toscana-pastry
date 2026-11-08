"""Acceptance + scale-parity tests for the calc money contract (S1/S3).

Fixture "Torta corazón" (incident 2026-10-31, odd/tasks/
calc-money-and-editor-fixes.md): all three line families enter as the
same canonical unit — integer cents — and the engine must reproduce the
business-expected total: cost $16.880,00 -> final $29.178,29
(21% IVA, 30% margen, sin descuento, rounding none).

M2: no single line family may drift in scale; snapshots and the
recalculate endpoint must keep the three families comparable.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

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

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


async def _admin(client: AsyncClient) -> dict:
    response = await client.post("/api/v1/auth/login", json={"email": "admin@example.com"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.cookies['auth_token']}"}


async def _set_settings(client: AsyncClient, headers: dict, **overrides) -> None:
    payload = {
        "business_name": "Toscana Pastry",
        "main_currency_name": "Peso",
        "main_currency_symbol": "$",
        "default_margin_percent": "30",
        "default_discount_percent": "0",
        "default_tax_percent": "21",
        "rounding_mode": "none",
    }
    payload.update(overrides)
    response = await client.put("/api/v1/calc/settings", json=payload, headers=headers)
    assert response.status_code == 200, response.text


async def _create_material(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {"name": "Material"}
    payload.update(overrides)
    response = await client.post("/api/v1/calc/materials", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ─── M1-acceptance: fixture "Torta corazón" ─────────────────────────────
#
# 7 líneas de material (10.080,00 pesos) + trabajo 3.000/h × 120 min
# (6.000,00) + gas y luz 800 × 1 (800,00) = 16.880,00 pesos de costo.
# Margen 30%, descuento 0, IVA 21%, rounding none -> final 29.178,29.

TORTA_MATERIALS = [
    ("Fondant de chocolate", 240000),
    ("Crema para batir", 90000),
    ("Azucar impalpable", 48000),
    ("Mantequilla", 150000),
    ("Colorante rojo", 30000),
    ("Molde corazon", 200000),
    ("Empaque corazon", 250000),
]

# Derivado del motor B9 (price_base = cost / (1 - margen), redondeo
# half-up a ctvs por etapa):
TORTA_COSTS = {
    "product_total_cost": 1688000,
    "profit_amount": 723429,
    "discount_amount": 0,
    "adjusted_profit_amount": 723429,
    "tax_amount": 506400,
    "final_sale_price": 2917829,
}


async def _create_torta_corazon(client: AsyncClient, headers: dict) -> dict:
    materials = [
        await _create_material(
            client,
            headers,
            name=name,
            purchase_total_price=price_cents,
            package_quantity="1",
        )
        for name, price_cents in TORTA_MATERIALS
    ]
    payload = {
        "name": "Torta corazon",
        "discount_percent": "0",
        "materials": [
            {"material_id": m["id"], "quantity_used": "1"} for m in materials
        ],
        "labor": [
            {
                "activity_name": "Decoracion",
                "hourly_rate": 300000,
                "minutes_required": "120",
            }
        ],
        "extra_costs": [
            {"concept_name": "Gas y luz", "unit_cost": 80000, "quantity": "1"}
        ],
    }
    response = await client.post(
        "/api/v1/calc/products", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestTortaCorazonAcceptance:
    async def test_full_flow_totals_match_business_expectation(self, client):
        """M1-acceptance (S3): las tres familias en la misma escala
        (integer centavos) -> costo 1.688.000 ctvs y final 2.917.829 ctvs."""
        headers = await _admin(client)
        await _set_settings(client, headers)
        body = await _create_torta_corazon(client, headers)

        assert body["costs"] == TORTA_COSTS
        assert body["costs"]["product_total_cost"] == 1688000
        assert body["costs"]["final_sale_price"] == 2917829

    async def test_detail_and_recalculate_reproduce_totals(self, client):
        headers = await _admin(client)
        await _set_settings(client, headers)
        created = await _create_torta_corazon(client, headers)
        product_id = created["product"]["id"]

        detail = await client.get(
            f"/api/v1/calc/products/{product_id}", headers=headers
        )
        assert detail.status_code == 200
        assert detail.json()["costs"] == TORTA_COSTS

        recalculated = await client.post(
            f"/api/v1/calc/products/{product_id}/recalculate", headers=headers
        )
        assert recalculated.status_code == 200, recalculated.text
        assert recalculated.json()["costs"] == TORTA_COSTS


# ─── M2: paridad de escala entre las 3 familias de líneas ───────────────


class TestLineFamilyScaleParity:
    async def test_snapshots_keep_single_scale(self, client):
        """M2 (S1): unit_cost_snapshot (materiales), hourly_rate
        (trabajo) y unit_cost (extras) viajan en la misma escala (ctvs);
        recalculate reproduce el total sin deriva."""
        headers = await _admin(client)
        await _set_settings(client, headers)
        material = await _create_material(
            client,
            headers,
            name="Harina 000",
            unit_of_measure="kg",
            purchase_total_price=150000,  # 1.500,00 pesos por kg
            package_quantity="1",
        )
        assert material["unit_cost"] == 150000

        payload = {
            "name": "Torta paridad",
            "discount_percent": "0",
            "materials": [
                {"material_id": material["id"], "quantity_used": "2"}
            ],  # 3.000,00
            "labor": [
                {
                    "activity_name": "Coccion",
                    "hourly_rate": 60000,  # 600,00/h
                    "minutes_required": "60",  # 600,00
                }
            ],
            "extra_costs": [
                {"concept_name": "Envio", "unit_cost": 25000, "quantity": "1"}  # 250,00
            ],
        }
        response = await client.post(
            "/api/v1/calc/products", json=payload, headers=headers
        )
        assert response.status_code == 201, response.text
        created = response.json()

        # 3.000 + 600 + 250 = 3.850 pesos = 385.000 ctvs.
        assert created["costs"]["product_total_cost"] == 385000

        detail = (
            await client.get(
                f"/api/v1/calc/products/{created['product']['id']}", headers=headers
            )
        ).json()
        # GET detail: lineas a nivel superior (materials/labor/extra_costs).
        (mat,) = detail["materials"]
        (labor,) = detail["labor"]
        (extra,) = detail["extra_costs"]

        # Mismas magnitudes que lo enviado: ninguna familia ×100/÷100.
        assert mat["unit_cost_snapshot"] == 150000
        assert mat["line_total_cost"] == 300000
        assert labor["hourly_rate"] == 60000
        assert labor["line_total_cost"] == 60000
        assert extra["unit_cost"] == 25000
        assert extra["line_total_cost"] == 25000

        recalculated = await client.post(
            f"/api/v1/calc/products/{created['product']['id']}/recalculate",
            headers=headers,
        )
        assert recalculated.status_code == 200
        assert (
            recalculated.json()["costs"]["product_total_cost"] == 385000
        )

    async def test_string_money_payload_is_rejected(self, client):
        """S3: el borde de la API calc no adivina escalas: str/float en
        campos Money -> 422 (el motor nunca recibe dos escalas)."""
        headers = await _admin(client)
        await _set_settings(client, headers)
        material = await _create_material(
            client, headers, name="Azucar", purchase_total_price=50000
        )
        payload = {
            "name": "Torta str",
            "materials": [
                {"material_id": material["id"], "quantity_used": "1"}
            ],
            "labor": [
                {
                    "activity_name": "Coccion",
                    "hourly_rate": "60000",  # str: pesos? ctvs? -> 422
                    "minutes_required": "60",
                }
            ],
            "extra_costs": [
                {"concept_name": "Envio", "unit_cost": 25000, "quantity": "1"}
            ],
        }
        response = await client.post(
            "/api/v1/calc/products", json=payload, headers=headers
        )
        assert response.status_code == 422, response.text
