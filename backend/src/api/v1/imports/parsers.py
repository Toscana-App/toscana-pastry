from __future__ import annotations

import csv
import io
from typing import Iterable

_UTF8_BOM = b"\xef\xbb\xbf"


def detect_encoding(raw: bytes) -> str:
    if raw.startswith(_UTF8_BOM):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def decode_text(raw: bytes) -> tuple[str, str]:
    encoding = detect_encoding(raw)
    return raw.decode(encoding), encoding


def detect_delimiter(text: str) -> str:
    first_line = next(iter(text.splitlines()), "")
    semicolons = first_line.count(";")
    commas = first_line.count(",")
    return ";" if semicolons >= commas else ","


def parse_csv(text: str, delimiter: str) -> tuple[list[str], list[list[str]]]:
    if not text:
        return [], []
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    records = [rec for rec in reader if rec and any(cell.strip() for cell in rec)]
    if not records:
        return [], []
    headers = [header.strip() for header in records[0]]
    return headers, records[1:]


def rows_to_dicts(headers: list[str], rows: Iterable[list[str]]) -> list[dict[str, str]]:
    dicts: list[dict[str, str]] = []
    for row in rows:
        d: dict[str, str] = {}
        for index, header in enumerate(headers):
            value = row[index].strip() if index < len(row) else ""
            d[header] = value
        dicts.append(d)
    return dicts
