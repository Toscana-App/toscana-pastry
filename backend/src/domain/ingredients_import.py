import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from domain.models import STOCK_UNITS

_QTY_WITH_UNIT = re.compile(
    r"^(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(kg|g|L|ml|unidad)$",
    re.IGNORECASE,
)
_UNIT_CANONICAL = {unit.lower(): unit for unit in STOCK_UNITS}

_THOUSANDS_DOT_ONLY = re.compile(r"^(?!0\.)\d{1,3}(?:\.\d{3})+$")


class ImportLineError(ValueError):
    pass


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
        text = text.replace(".", "")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ImportLineError(f"{label} no es un numero: {raw!r}") from exc
    if value < 0:
        raise ImportLineError(f"{label} no puede ser negativo")
    return value


def parse_import_line(line: str) -> ParsedImportLine:
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
