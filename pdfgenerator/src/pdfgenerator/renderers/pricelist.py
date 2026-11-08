"""Render de la lista de precios en PDF (WeasyPrint).

Movido de ``backend/src/api/v1/products/router.py`` (``_build_pdf_html`` +
``pricelist_pdf``) al binario ``pdfgenerator``. El HTML se construye aqui;
``core-api`` solo arma las filas y pide los bytes por HTTP.

WeasyPrint requiere Pango/GObject en el sistema; si no esta disponible el
endpoint devuelve un error controlado (no un crash).
"""
from __future__ import annotations

from html import escape

from ..schemas import PricelistRow


def _build_pdf_html(rows: list[PricelistRow], audience_label: str) -> str:
    """Construye HTML para renderizar como PDF con WeasyPrint.

    Escapa ``name`` y ``unit`` con ``html.escape`` para prevenir inyeccion de
    markup. El ``audience_label`` es controlado por la aplicacion.
    """
    rows_html = ""
    for row in rows:
        name = escape(row.name)
        unit = escape(row.unit)
        rows_html += (
            f"<tr><td>{name}</td>"
            f"<td>{unit}</td>"
            f"<td>{escape(row.price)}</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: sans-serif; margin: 2em; }}
        h1 {{ color: #333; border-bottom: 2px solid #e8d5b7; padding-bottom: 0.5em; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
        th {{ background: #f5ebe0; padding: 0.5em; text-align: left; border-bottom: 2px solid #ddd; }}
        td {{ padding: 0.5em; border-bottom: 1px solid #eee; }}
        .audience {{ color: #666; font-style: italic; }}
    </style>
</head>
<body>
    <h1>Lista de Precios</h1>
    <p class="audience">Audiencia: {escape(audience_label)}</p>
    <table>
        <thead>
            <tr><th>Producto</th><th>Unidad</th><th>Precio</th></tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>"""


def render_pricelist(rows: list[PricelistRow], audience_label: str) -> bytes:
    """Renderiza la lista de precios a bytes de PDF (WeasyPrint)."""
    from weasyprint import HTML  # lazy: Pango/GObject

    html_content = _build_pdf_html(rows, audience_label)
    return HTML(string=html_content).render().write_pdf()
