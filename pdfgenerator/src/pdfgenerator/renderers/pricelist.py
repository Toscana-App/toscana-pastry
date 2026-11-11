from __future__ import annotations

from ..schemas import PricelistRow
from .document import render_document_pdf


def render_pricelist(
    rows: list[PricelistRow],
    audience_label: str,
    business_name: str = "",
    footer_text: str = "",
) -> bytes:
    meta = [
        ("Productos", str(len(rows))),
        ("Moneda", "ARS"),
        ("Audiencia", audience_label),
        ("Condición", "Precios finales"),
    ]
    return render_document_pdf(
        title="Lista de precios",
        business_name=business_name,
        footer_text=footer_text
        or "Precios expresados en pesos argentinos. Vigentes a la fecha de emisión.",
        document_kind="Lista de precios",
        meta=meta,
        columns=["Producto", "Categoría", "Precio"],
        rows=[[row.name, row.category, row.price] for row in rows],
        numeric_columns=(2,),
        column_widths=("68%", "16%", "16%"),
        section_title="Catálogo",
        empty_message="La lista no tiene productos publicados.",
    )
