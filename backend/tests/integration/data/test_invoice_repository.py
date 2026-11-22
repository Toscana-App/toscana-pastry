"""T2 — Repositorio de comprobantes ARCA (corre en CI con Postgres).

Cubre D3 (un comprobante por pedido, único por punto/tipo/número),
RF-P13-03 (persistencia de la emisión) y el singleton de settings.
"""

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from data.models import InvoicingSettingsORM, OrderORM
from data.repositories.sql_invoice_repository import SQLInvoiceRepository
from domain.invoicing import (
    DOC_TIPO_CONSUMIDOR_FINAL,
    TIPO_CBTE_FACTURA_C,
    Invoice,
    InvoiceItem,
    InvoicingSettings,
)

FECHA = datetime.date(2026, 11, 10)
CAE_VTO = datetime.date(2026, 11, 20)


def _invoice(order_id: str = "ord-1", **overrides) -> Invoice:
    base = {
        "order_id": order_id,
        "punto_venta": 1,
        "tipo_cbte": TIPO_CBTE_FACTURA_C,
        "numero": 7,
        "cae": "12345678901234",
        "cae_vto": CAE_VTO,
        "fecha": FECHA,
        "imp_total": "5200.00",
        "receptor_doc_tipo": DOC_TIPO_CONSUMIDOR_FINAL,
        "receptor_doc_nro": 0,
        "receptor_nombre": "Maria",
    }
    base.update(overrides)
    return Invoice(**base)


def _item(descripcion: str = "Bizmerengue 20", cantidad: str = "20",
          precio: str = "1000.00", position: int = 1) -> InvoiceItem:
    return InvoiceItem(descripcion=descripcion, cantidad=Decimal(cantidad),
                       precio_unit=precio, position=position)


async def _seed_order(db_session, code: str = "TPTEST01") -> str:
    order_id = f"ord-{code.lower()}"
    db_session.add(
        OrderORM(
            id=order_id,
            customer_id="cust-1",
            code=code,
            date=datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.UTC),
            customer_name="Maria",
        )
    )
    await db_session.commit()
    return order_id


class TestSaveInvoice:
    async def test_save_and_get_roundtrip(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        order_id = await _seed_order(db_session)
        saved = await repo.save_invoice(_invoice(order_id=order_id))
        got = await repo.get(saved.id)
        assert got is not None
        assert got.id == saved.id
        assert got.order_id == order_id
        assert got.punto_venta == 1
        assert got.tipo_cbte == TIPO_CBTE_FACTURA_C
        assert got.numero == 7
        assert got.cae == "12345678901234"
        assert got.cae_vto == CAE_VTO
        assert got.fecha == FECHA
        assert got.imp_total == "5200.00"
        assert got.estado == "A"
        assert got.receptor_doc_tipo == DOC_TIPO_CONSUMIDOR_FINAL
        assert got.receptor_doc_nro == 0
        assert got.receptor_nombre == "Maria"

    async def test_save_with_items_and_obs(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        order_id = await _seed_order(db_session)
        inv = _invoice(order_id=order_id, obs=("10015: Fecha inválida", "otra obs"))
        saved = await repo.save_invoice(inv, items=[
            _item("Bizmerengue 20", "20", "1000.00", 1),
            _item("Ensaymada", "4", "1500.00", 2),
        ])
        got = await repo.get(saved.id)
        assert got is not None
        assert got.obs == ("10015: Fecha inválida", "otra obs")
        assert len(got.items) == 2
        assert got.items[0].descripcion == "Bizmerengue 20"
        assert got.items[0].cantidad == Decimal(20)
        assert got.items[0].precio_unit == "1000.00"
        assert got.items[0].position == 1
        assert got.items[1].descripcion == "Ensaymada"

    async def test_get_unknown_returns_none(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        assert await repo.get("inexistente") is None

    async def test_items_empty(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        order_id = await _seed_order(db_session)
        saved = await repo.save_invoice(_invoice(order_id=order_id))
        got = await repo.get(saved.id)
        assert got is not None
        assert got.items == ()


class TestUnicoPorPedido:
    async def test_get_by_order(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        order_id = await _seed_order(db_session)
        saved = await repo.save_invoice(_invoice(order_id=order_id))
        got = await repo.get_by_order(order_id)
        assert got is not None
        assert got.id == saved.id

    async def test_get_by_order_empty(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        order_id = await _seed_order(db_session)
        assert await repo.get_by_order(order_id) is None

    async def test_order_id_unique(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        order_id = await _seed_order(db_session)
        await repo.save_invoice(_invoice(order_id=order_id))
        # un segundo comprobante para el mismo pedido viola la unique
        with pytest.raises(IntegrityError):
            await repo.save_invoice(_invoice(order_id=order_id, numero=8))

    async def test_unica_por_combo_punto_tipo_numero(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        o1 = await _seed_order(db_session, "TPTEST01")
        o2 = await _seed_order(db_session, "TPTEST02")
        await repo.save_invoice(_invoice(order_id=o1))
        # mismo (punto_venta, tipo_cbte, numero) con otro pedido → viola la unique
        with pytest.raises(IntegrityError):
            await repo.save_invoice(_invoice(order_id=o2))


class TestList:
    async def test_list_sin_filtro(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        o1 = await _seed_order(db_session, "TPTEST01")
        o2 = await _seed_order(db_session, "TPTEST02")
        await repo.save_invoice(_invoice(order_id=o1, numero=1))
        await repo.save_invoice(_invoice(order_id=o2, numero=2))
        items, total = await repo.list()
        assert total == 2
        assert {i.order_id for i in items} == {o1, o2}

    async def test_list_filtrado_por_order(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        o1 = await _seed_order(db_session, "TPTEST01")
        o2 = await _seed_order(db_session, "TPTEST02")
        await repo.save_invoice(_invoice(order_id=o1, numero=1))
        await repo.save_invoice(_invoice(order_id=o2, numero=2))
        items, total = await repo.list(order_id=o2)
        assert total == 1
        assert items[0].order_id == o2

    async def test_list_pagination(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        for n in range(1, 6):
            order_id = await _seed_order(db_session, f"TPTEST{n:02d}")
            await repo.save_invoice(_invoice(order_id=order_id, numero=n))
        page1, total = await repo.list(page=1, page_size=3)
        assert total == 5
        assert len(page1) == 3
        page2, _ = await repo.list(page=2, page_size=3)
        assert len(page2) == 2
        assert page1[0].id != page2[0].id


class TestSettings:
    async def test_get_sin_fila(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        assert await repo.get_settings() is None

    async def test_save_and_get(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        settings = InvoicingSettings(
            cuit="30123456789",
            punto_venta=1,
            razon_social="PASTA FRESCA SAS",
            domicilio="Av. Corrientes 123",
            categoria_monotributo="f",
            inicio_actividades="01/05/2020",
        )
        await repo.save_settings(settings)
        got = await repo.get_settings()
        assert got is not None
        assert got.cuit == "30123456789"
        assert got.punto_venta == 1
        assert got.razon_social == "PASTA FRESCA SAS"
        assert got.domicilio == "Av. Corrientes 123"
        assert got.categoria_monotributo == "F"
        assert got.inicio_actividades == "01/05/2020"

    async def test_save_actualiza_singleton(self, db_session):
        repo = SQLInvoiceRepository(db_session)
        await repo.save_settings(InvoicingSettings(cuit="30123456789", punto_venta=1))
        updated = await repo.save_settings(InvoicingSettings(cuit="30123456789", punto_venta=2,
                                                            razon_social="Cambio SA"))
        got = await repo.get_settings()
        assert got is not None
        assert got.punto_venta == 2
        assert got.razon_social == "Cambio SA"
        # sigue habiendo UNA sola fila (singleton)
        count = (await db_session.execute(
            select(func.count()).select_from(InvoicingSettingsORM)
        )).scalar_one()
        assert count == 1
        assert updated.punto_venta == 2
