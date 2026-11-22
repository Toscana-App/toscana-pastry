"""P13 — Repositorio de comprobantes ARCA (SQLAlchemy async).

Persistencia de ``invoices`` / ``invoice_items`` (RF-P13-03) y del
singleton de settings de facturación.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data.models import InvoiceItemORM, InvoiceORM, InvoicingSettingsORM
from domain.invoicing import Invoice, InvoiceItem, InvoicingSettings


def _to_item(orm: InvoiceItemORM) -> InvoiceItem:
    return InvoiceItem(
        id=orm.id,
        descripcion=orm.descripcion,
        cantidad=Decimal(orm.cantidad),
        precio_unit=orm.precio_unit,
        position=orm.position or 0,
    )


def _to_invoice(orm: InvoiceORM) -> Invoice:
    obs = tuple(line.strip() for line in (orm.obs or "").splitlines() if line.strip())
    items = tuple(
        _to_item(item) for item in sorted(orm.invoice_items, key=lambda i: i.position or 0)
    )
    return Invoice(
        id=orm.id,
        order_id=orm.order_id,
        punto_venta=orm.punto_venta,
        tipo_cbte=orm.tipo_cbte,
        numero=orm.numero,
        cae=orm.cae,
        cae_vto=orm.cae_vto,
        fecha=orm.fecha,
        imp_total=orm.imp_total,
        condicion_iva=orm.condicion_iva or "Responsable Monotributo",
        estado=orm.estado,
        obs=obs,
        receptor_doc_tipo=orm.receptor_doc_tipo,
        receptor_doc_nro=orm.receptor_doc_nro,
        receptor_nombre=orm.receptor_nombre,
        created_at=orm.created_at,
        items=items,
    )


class SQLInvoiceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_invoice(
        self, invoice: Invoice, items: list[InvoiceItem] | None = None
    ) -> Invoice:
        """Persiste el comprobante y sus ítems (RF-P13-03)."""
        self.session.add(
            InvoiceORM(
                id=invoice.id,
                order_id=invoice.order_id,
                punto_venta=invoice.punto_venta,
                tipo_cbte=invoice.tipo_cbte,
                numero=invoice.numero,
                cae=invoice.cae,
                cae_vto=invoice.cae_vto,
                fecha=invoice.fecha,
                imp_total=invoice.imp_total,
                condicion_iva=invoice.condicion_iva,
                estado=invoice.estado,
                obs="\n".join(invoice.obs),
                receptor_doc_tipo=invoice.receptor_doc_tipo,
                receptor_doc_nro=invoice.receptor_doc_nro,
                receptor_nombre=invoice.receptor_nombre,
                created_at=invoice.created_at,
            )
        )
        for item in items or []:
            self.session.add(
                InvoiceItemORM(
                    id=item.id,
                    invoice_id=invoice.id,
                    descripcion=item.descripcion,
                    cantidad=item.cantidad,
                    precio_unit=item.precio_unit,
                    position=item.position,
                )
            )
        await self.session.commit()
        return invoice

    async def get(self, invoice_id: str) -> Invoice | None:
        result = await self.session.execute(
            select(InvoiceORM)
            .where(InvoiceORM.id == invoice_id)
            .options(selectinload(InvoiceORM.invoice_items))
            .limit(1)
        )
        orm = result.scalars().first()
        return _to_invoice(orm) if orm else None

    async def get_by_order(self, order_id: str) -> Invoice | None:
        result = await self.session.execute(
            select(InvoiceORM)
            .where(InvoiceORM.order_id == order_id)
            .options(selectinload(InvoiceORM.invoice_items))
            .limit(1)
        )
        orm = result.scalars().first()
        return _to_invoice(orm) if orm else None

    async def list(
        self,
        order_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Invoice], int]:
        filters = []
        if order_id:
            filters.append(InvoiceORM.order_id == order_id)
        count_result = await self.session.execute(
            select(func.count()).select_from(InvoiceORM).where(*filters)
        )
        total = count_result.scalar_one()
        result = await self.session.execute(
            select(InvoiceORM)
            .where(*filters)
            .options(selectinload(InvoiceORM.invoice_items))
            .order_by(
                InvoiceORM.fecha.desc(),
                InvoiceORM.numero.desc(),
                InvoiceORM.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [_to_invoice(orm) for orm in result.scalars().all()], total

    async def get_settings(self) -> InvoicingSettings | None:
        orm = await self.session.get(InvoicingSettingsORM, "singleton")
        if orm is None:
            return None
        return InvoicingSettings(
            cuit=orm.cuit,
            punto_venta=orm.punto_venta,
            razon_social=orm.razon_social or "",
            domicilio=orm.domicilio or "",
            condicion_iva=orm.condicion_iva or "Responsable Monotributo",
            categoria_monotributo=orm.categoria_monotributo or "",
            ingresos_brutos=orm.ingresos_brutos or "",
            inicio_actividades=orm.inicio_actividades or "",
        )

    async def save_settings(self, settings: InvoicingSettings) -> InvoicingSettings:
        """Crea o actualiza la única fila de settings (id='singleton')."""
        orm = await self.session.get(InvoicingSettingsORM, "singleton")
        values = {
            "cuit": settings.cuit,
            "punto_venta": settings.punto_venta,
            "razon_social": settings.razon_social,
            "domicilio": settings.domicilio,
            "condicion_iva": settings.condicion_iva,
            "categoria_monotributo": settings.categoria_monotributo,
            "ingresos_brutos": settings.ingresos_brutos,
            "inicio_actividades": settings.inicio_actividades,
        }
        if orm is None:
            orm = InvoicingSettingsORM(id="singleton", **values)
            self.session.add(orm)
        else:
            for key, value in values.items():
                setattr(orm, key, value)
        await self.session.commit()
        return settings
