"""Router para exportación de lista de precios por audiencia (S3 — T4).

Endpoints:
  GET /products/pricelist/csv?audience=revendedores|consumidor_final
  GET /products/pricelist/pdf?audience=revendedores|consumidor_final
  GET /products?audience=revendedores|consumidor_final

Gate por rol:
  - admin: ambas audiencias
  - negocio: solo revendedores (consumidor_final → 403)
  - cliente: solo consumidor_final (revendedores → 403)

Reutiliza ``compute_dual_pricing`` / ``resolve_audience`` de
``domain.pricing_service`` para la resolución de audiencia y el cálculo
del precio derivado — la regla de negocio tiene un único hogar.
"""
import asyncio
import logging
from decimal import Decimal
from html import escape
from io import StringIO

import csv as csv_module
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response

from api.v1.dependencies import require_role
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.pricing.schemas import Audience
from api.v1.settings.dependencies import get_settings_repository
from domain.models import User, UserRole
from domain.pricing_service import (
    AudienceForbiddenError,
    derive_audience_price,
    resolve_audience,
)
from domain.repositories import IngredientRepository, SettingsRepository
from domain.use_cases import GetSettings

router = APIRouter(prefix="/products", tags=["products"])
logger = logging.getLogger(__name__)

_LIST_PAGE_SIZE = 500
_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 500
_FORMULA_PREFIXES = ("=", "+", "-", "@", "	")


def _csv_safe(value: str) -> str:
    """Neutraliza formula injection: un texto que empieza con ``= + - @`` o
    tab se prefija con ``'`` para que Excel/Sheets no lo ejecuten."""
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


async def _list_all_ingredients(ingredient_repo: IngredientRepository) -> list:
    """Recorre todas las paginas del repositorio: sin truncado silencioso."""
    products: list = []
    page = 1
    while True:
        batch, total = await ingredient_repo.list(
            q=None, status=None, page=page, page_size=_LIST_PAGE_SIZE
        )
        products.extend(batch)
        if not batch or len(products) >= total:
            return products
        page += 1


def _resolve_or_403(user: User, audience: str) -> str:
    try:
        return resolve_audience(user.role, audience)
    except AudienceForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


async def _build_audience_rows(
    ingredient_repo: IngredientRepository,
    settings_repo: SettingsRepository,
    resolved: str,
    page: int | None = None,
    page_size: int | None = None,
) -> tuple[list[tuple], int]:
    """Devuelve ``(filas, total)`` con ``(ingredient, precio_para_la_audiencia)``;
    unico lugar donde se aplica ``derive_audience_price``.

    Sin ``page``/``page_size`` devuelve TODOS los productos (exports, y el
    listado por defecto). Con alguno de los dos, devuelve solo esa pagina y
    ``total`` sigue siendo el total de productos.
    """
    settings = await GetSettings(settings_repo).execute()
    if page is None and page_size is None:
        products = await _list_all_ingredients(ingredient_repo)
        total = len(products)
    else:
        products, total = await ingredient_repo.list(
            q=None, status=None, page=page or 1, page_size=page_size or _DEFAULT_PAGE_SIZE
        )
    rows = [
        (
            product,
            derive_audience_price(
                product.price_per_unit, settings.consumer_markup_pct, resolved
            ),
        )
        for product in products
    ]
    return rows, total


def _build_csv(rows: list[dict[str, str]]) -> str:
    """Construye un CSV usando ``csv.writer`` para escapar correctamente
    comas, comillas y saltos de línea en los valores.
    """
    output = StringIO()
    header = list(rows[0].keys())
    writer = csv_module.writer(output, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_csv_safe(row[h]) for h in header])
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
    resolved = _resolve_or_403(current_user, audience)
    priced, _ = await _build_audience_rows(ingredient_repo, settings_repo, resolved)

    rows = []
    for product, price in priced:
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
    page: int | None = Query(None, ge=1, description="Pagina (opcional)"),
    page_size: int | None = Query(
        None, ge=1, le=_MAX_PAGE_SIZE, description="Tamano de pagina (opcional)"
    ),
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
            "total": int   # total de productos, no el de la pagina
        }

    ``page`` / ``page_size`` son opcionales; sin ellos se devuelven todos.
    """
    resolved = _resolve_or_403(current_user, audience)
    priced, total = await _build_audience_rows(
        ingredient_repo, settings_repo, resolved, page, page_size
    )

    product_rows = []
    for product, price in priced:
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
        "total": total,
    }


def _pdf_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": "Service Unavailable",
            "status": status.HTTP_503_SERVICE_UNAVAILABLE,
            "detail": "PDF generation is temporarily unavailable.",
        },
    )


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
    resolved = _resolve_or_403(current_user, audience)
    priced, _ = await _build_audience_rows(ingredient_repo, settings_repo, resolved)

    audience_label = "Revendedores" if resolved == "revendedores" else "Consumidor final"
    product_rows = []
    for product, price in priced:
        product_rows.append({
            "name": product.name,
            "unit": product.unit,
            "price": f"${price}",
            "audience_label": audience_label,
        })

    html_content = _build_pdf_html(product_rows)
    # Lazy import: WeasyPrint requires Pango/GObject on Windows. El detalle
    # del error va solo al log; el cliente recibe un problema generico.
    try:
        from weasyprint import HTML

        # Render CPU-bound: fuera del event loop.
        pdf_bytes = await asyncio.to_thread(
            lambda: HTML(string=html_content).render().write_pdf()
        )
    except OSError as e:
        logger.error("PDF render failed: %s", e)
        return _pdf_unavailable()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="pricelist_{resolved}.pdf"'
        },
    )
