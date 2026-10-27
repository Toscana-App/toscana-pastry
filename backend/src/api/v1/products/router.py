"""Price-list export router by audience (S3 — T4).

Endpoints:
  GET /products/pricelist/csv?audience=revendedores|consumidor_final
  GET /products/pricelist/pdf?audience=revendedores|consumidor_final
  GET /products?audience=revendedores|consumidor_final

Role gate:
  - admin: both audiences
  - negocio: revendedores only (consumidor_final → 403)
  - cliente: consumidor_final only (revendedores → 403)

Reutiliza ``compute_dual_pricing`` / ``_resolve_audience`` de
``domain.pricing_service`` para la resolución de audiencia y el cálculo
del precio derivado — la regla de negocio tiene un único hogar.
"""
from decimal import Decimal
from html import escape
from io import StringIO

import csv as csv_module
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from api.v1.dependencies import require_role
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.pricing.schemas import Audience
from api.v1.settings.dependencies import get_settings_repository
from domain.models import User, UserRole
from domain.pricing_service import (
    AudienceForbiddenError,
    derive_audience_price,
    _resolve_audience,
)
from domain.repositories import IngredientRepository, SettingsRepository
from domain.use_cases import GetSettings

router = APIRouter(prefix="/products", tags=["products"])


def _build_csv(rows: list[dict[str, str]]) -> str:
    """Construye un CSV usando ``csv.writer`` para escapar correctamente
    comas, comillas y saltos de línea en los valores.
    """
    output = StringIO()
    header = list(rows[0].keys())
    writer = csv_module.writer(output, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row[h] for h in header])
    return output.getvalue()


def _build_pdf_html(product_rows: list[dict[str, str]]) -> str:
    """Construye HTML para renderizar como PDF con WeasyPrint.

    Escapa ``name`` y ``unit`` con ``html.escape`` para prevenir
    inyección de markup. El ``audience_label`` es controlado por
    la aplicación y no necesita escapado.
    """
    rows_html = ""
    for row in product_rows:
        name = escape(row["name"])
        unit = escape(row["unit"])
        rows_html += (
            f"<tr><td>{name}</td>"
            f"<td>{unit}</td>"
            f"<td>{escape(row['price'])}</td></tr>\n"
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
    <p class="audience">Audiencia: {product_rows[0].get('audience_label', 'revendedores')}</p>
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


@router.get("/pricelist/csv")
async def pricelist_csv(
    audience: Audience = Query(..., description="Audiencia de precios"),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.NEGOCIO, UserRole.CUSTOMER)
    ),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    """Exporta la lista de precios en CSV para la audiencia del rol.

    - admin: ambas audiencias.
    - negocio: solo revendedores.
    - cliente: solo consumidor_final.
    """
    # Resolve audience via domain service (S3 — T4)
    try:
        resolved = _resolve_audience(current_user.role, audience)
    except AudienceForbiddenError as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    settings = await GetSettings(settings_repo).execute()

    # Get all products (ingredients)
    products, _ = await ingredient_repo.list(q=None, status=None, page=1, page_size=1000)

    # Build CSV rows using domain price computation
    rows = []
    for product in products:
        price = derive_audience_price(
            product.price_per_unit,
            settings.consumer_markup_pct,
            resolved,
        )
        rows.append({
            "name": product.name,
            "unit": product.unit,
            "price": f"${price}",
        })

    csv_content = _build_csv(rows)
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="pricelist_{resolved}.csv"'
        },
    )


def _stock_status(stock_qty: Decimal, low_stock_threshold: Decimal) -> str:
    """Deriva el status de stock desde los campos del ingrediente.

    - ``EMPTY``: stock_qty == 0
    - ``LOW``: 0 < stock_qty <= low_stock_threshold
    - ``OK``: stock_qty > low_stock_threshold
    """
    if stock_qty == 0:
        return "EMPTY"
    if stock_qty <= low_stock_threshold:
        return "LOW"
    return "OK"


@router.get("")
async def list_products(
    audience: Audience = Query(..., description="Audiencia de precios"),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.NEGOCIO, UserRole.CUSTOMER)
    ),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    """Lista productos con el precio derivado para la audiencia del rol.

    - admin: ambas audiencias.
    - negocio: solo revendedores.
    - cliente: solo consumidor_final.

    Response::
        {
            "audience": "revendedores" | "consumidor_final",
            "products": [
                {"id": str, "name": str, "unit": str,
                 "price_per_unit": str, "status": str}
            ],
            "total": int
        }
    """
    # Resolve audience via domain service
    try:
        resolved = _resolve_audience(current_user.role, audience)
    except AudienceForbiddenError as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    settings = await GetSettings(settings_repo).execute()

    # Get all products (ingredients) with page-size cap
    products, _ = await ingredient_repo.list(q=None, status=None, page=1, page_size=1000)

    # Build response rows using domain price computation
    product_rows = []
    for product in products:
        price = derive_audience_price(
            product.price_per_unit,
            settings.consumer_markup_pct,
            resolved,
        )
        product_rows.append({
            "id": product.id,
            "name": product.name,
            "unit": product.unit,
            "price_per_unit": str(price),
            "status": _stock_status(product.stock_qty, product.low_stock_threshold),
        })

    return {
        "audience": resolved,
        "products": product_rows,
        "total": len(product_rows),
    }


@router.get("/pricelist/pdf")
async def pricelist_pdf(
    audience: Audience = Query(..., description="Audiencia de precios"),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.NEGOCIO, UserRole.CUSTOMER)
    ),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    """Exporta la lista de precios en PDF para la audiencia del rol.

    - admin: ambas audiencias.
    - negocio: solo revendedores.
    - cliente: solo consumidor_final.

    Renderiza con WeasyPrint (requiere Pango en Windows).
    """
    # Resolve audience via domain service (S3 — T4)
    try:
        resolved = _resolve_audience(current_user.role, audience)
    except AudienceForbiddenError as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    settings = await GetSettings(settings_repo).execute()

    # Get all products (ingredients)
    products, _ = await ingredient_repo.list(q=None, status=None, page=1, page_size=1000)

    # Build PDF rows using domain price computation
    audience_label = "Revendedores" if resolved == "revendedores" else "Consumidor final"
    product_rows = []
    for product in products:
        price = derive_audience_price(
            product.price_per_unit,
            settings.consumer_markup_pct,
            resolved,
        )
        product_rows.append({
            "name": product.name,
            "unit": product.unit,
            "price": f"${price}",
            "audience_label": audience_label,
        })

    html_content = _build_pdf_html(product_rows)
    # Lazy import: WeasyPrint requires Pango/GObject on Windows.
    # If unavailable, the error surfaces here with the exact OS message.
    try:
        from weasyprint import HTML
    except OSError as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"WeasyPrint no puede renderizar: {e}",
        ) from e

    pdf_bytes = HTML(string=html_content).render().write_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="pricelist_{resolved}.pdf"'
        },
    )
