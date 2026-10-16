"""Importación por lista (RF-P2-07): parsing tolerante de líneas como
"harina 0000, 5, 2800". Función pura, sin I/O.

Formatos aceptados por línea:
- "nombre, cantidad, precio"          (unidad por defecto "unidad")
- "nombre, cantidad UNIDAD, precio"   ("1 L", "1,5 kg")
- "nombre, cantidad, unidad, precio"

Decimales con coma (convención argentina) o punto. El "." actúa como separador
de miles cuando la coma también está presente ("1.000,5") y también cuando
agrupa de a tres dígitos sin coma ("2.800" = 2800, no 2,8).
"""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from domain.models import STOCK_UNITS

# Cantidad con unidad adjunta: "1 L", "1,5 kg", "1.000,5 L" (convención
# argentina: punto de miles + coma decimal). La primera alternativa cubre
# los miles; la segunda, el numero simple o decimal cualquiera.
_QTY_WITH_UNIT = re.compile(
    r"^(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(kg|g|L|ml|unidad)$",
    re.IGNORECASE,
)
_UNIT_CANONICAL = {unit.lower(): unit for unit in STOCK_UNITS}

# Punto como separador de miles sin coma decimal ("2.800", "1.234.567").
# El lookahead descarta "0.500" y "0.5", donde el punto solo puede ser
# decimal. Sin esta rama "3.000" se leía como 3 (error x1000 silencioso
# en dinero y cantidad).
_THOUSANDS_DOT_ONLY = re.compile(r"^(?!0\.)\d{1,3}(?:\.\d{3})+$")


class ImportLineError(ValueError):
    """La línea no se pudo parsear. `message` es apta para el usuario."""


@dataclass(frozen=True)
class ParsedImportLine:
    name: str
    qty: Decimal
    price_per_unit: Decimal
    unit: str


def _to_decimal(raw: str, label: str) -> Decimal:
    text = raw.strip()
    if not text:
        raise ImportLineError(f"{label} vacio")
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif _THOUSANDS_DOT_ONLY.match(text):
        # Convención es-AR: "2.800" son dos mil ochocientos.
        text = text.replace(".", "")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ImportLineError(f"{label} no es un numero: {raw!r}") from exc
    if value < 0:
        raise ImportLineError(f"{label} no puede ser negativo")
    return value


def parse_import_line(line: str) -> ParsedImportLine:
    # Separador humano: coma + espacio. Una coma decimal ("1,5 kg") NO
    # lleva espacio despues de la coma, asi que no rompe el split. Si la
    # linea no tiene espacios tras las comas, se reintenta con coma sola.
    parts = [part.strip() for part in line.split(", ")]
    if len(parts) == 1:
        parts = [part.strip() for part in line.split(",")]
    if len(parts) == 4:
        name, qty_raw, unit_raw, price_raw = parts
    elif len(parts) == 3:
        name, qty_raw, price_raw = parts
        unit_raw = "unidad"
        match = _QTY_WITH_UNIT.match(qty_raw)
        if match:
            qty_raw, unit_raw = match.group(1), match.group(2)
        else:
            # "5 onzas" (unidad desconocida): extraer el token final para
            # reportar el error de unidad, no el de cantidad.
            split = qty_raw.rsplit(maxsplit=1)
            if len(split) == 2:
                qty_raw, unit_raw = split
    else:
        raise ImportLineError("se esperan 3 campos: nombre, cantidad, precio")
    if not name:
        raise ImportLineError("nombre vacio")
    unit = _UNIT_CANONICAL.get(unit_raw.strip().lower())
    if unit is None:
        raise ImportLineError(
            f"unidad invalida: {unit_raw!r} (esperado: {'/'.join(STOCK_UNITS)})"
        )
    return ParsedImportLine(
        name=name,
        qty=_to_decimal(qty_raw, "cantidad"),
        price_per_unit=_to_decimal(price_raw, "precio"),
        unit=unit,
    )
