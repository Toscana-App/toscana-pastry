"""Parsers puros de CSV (RF-CSV-10, RNF-CSV-08).

Sin I/O: solo bytes -> texto, deteccion de separador y parsing de filas. Se
toleran los dos separadores mas usados en Argentina (``;`` y ``,``) y los dos
encodings mas comunes en planillas de Excel (UTF-8 con BOM y Latin-1/CP1252).
"""
from __future__ import annotations

import csv
import io
from typing import Iterable

# BOM de UTF-8 (3 bytes) que Excel agrega al exportar en UTF-8.
_UTF8_BOM = b"\xef\xbb\xbf"


def detect_encoding(raw: bytes) -> str:
    """Detecta el encoding mas probable: BOM -> utf-8-sig, si no UTF-8 valido
    -> utf-8, si no -> latin-1 (siempre decodificable)."""
    if raw.startswith(_UTF8_BOM):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def decode_text(raw: bytes) -> tuple[str, str]:
    """Decodifica ``raw`` y devuelve ``(texto, encoding)`` (BOM retirado)."""
    encoding = detect_encoding(raw)
    return raw.decode(encoding), encoding


def detect_delimiter(text: str) -> str:
    """Elije el separador contando ``;`` vs ``,`` en la primera fila.

    Empate o ausencia -> ``;`` (el mas comun en planillas argentinas).
    """
    first_line = next(iter(text.splitlines()), "")
    semicolons = first_line.count(";")
    commas = first_line.count(",")
    return ";" if semicolons >= commas else ","


def parse_csv(text: str, delimiter: str) -> tuple[list[str], list[list[str]]]:
    """Devuelve ``(headers, filas)``.

    La primera fila no vacia es el encabezado (celdas con espacios recortados).
    Las filas totalmente vacias se ignoran. ``filas`` es una lista de listas de
    strings (las celdas ya se recortan en :func:`rows_to_dicts`).
    """
    if not text:
        return [], []
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    records = [rec for rec in reader if rec and any(cell.strip() for cell in rec)]
    if not records:
        return [], []
    headers = [header.strip() for header in records[0]]
    return headers, records[1:]


def rows_to_dicts(headers: list[str], rows: Iterable[list[str]]) -> list[dict[str, str]]:
    """Mapea cada fila a ``{header: celda}`` (celdas recortadas).

    Celdas faltantes -> ``""``; celdas sobrantes se descartan.
    """
    dicts: list[dict[str, str]] = []
    for row in rows:
        d: dict[str, str] = {}
        for index, header in enumerate(headers):
            value = row[index].strip() if index < len(row) else ""
            d[header] = value
        dicts.append(d)
    return dicts
