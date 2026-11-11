from __future__ import annotations

import datetime
import html
from typing import Sequence

SERIF = 'Georgia, "Bitstream Charter", "DejaVu Serif", serif'
SANS = '"Helvetica Neue", Helvetica, Arial, "Liberation Sans", "DejaVu Sans", sans-serif'

INK = "#1c1718"
INK_SOFT = "#4a4241"
MUTED = "#7d7371"
FAINT = "#a89e9b"
HAIRLINE = "#e7dfda"
HAIRLINE_SOFT = "#efe8e4"
ZEBRA = "#fbf8f6"
ACCENT = "#ff7078"

_BASE_CSS = f"""
* {{ box-sizing: border-box; }}
html {{ font-family: {SANS}; font-size: 9pt; line-height: 1.45; color: {INK}; }}
body {{ margin: 0; }}
.band {{ width: 100%; border-collapse: collapse; }}
.band td {{ padding: 0; border: 0; }}
.masthead td {{ vertical-align: bottom; }}
.masthead__keep {{ width: 100%; }}
.brand__name {{ font-family: {SERIF}; font-size: 15pt; letter-spacing: -0.01em; }}
.brand__kind {{ display: block; margin-top: 1.5mm; font-size: 6.6pt; letter-spacing: 0.14em; text-transform: uppercase; color: {MUTED}; }}
.masthead__right {{ text-align: right; white-space: nowrap; }}
.masthead__label {{ display: block; font-size: 7.4pt; color: {INK_SOFT}; }}
.masthead__stamp {{ display: block; margin-top: 1.2mm; font-size: 7pt; color: {MUTED}; }}
.rule {{ height: 1.5pt; background: {ACCENT}; margin: 4mm 0 7mm; }}
.title-block td {{ vertical-align: baseline; }}
.title-block__keep {{ width: 100%; }}
h1 {{ margin: 0; font-family: {SERIF}; font-size: 25pt; font-weight: 400; letter-spacing: -0.02em; line-height: 1.08; }}
.subtitle {{ margin: 2.5mm 0 0; font-size: 8.8pt; color: {INK_SOFT}; max-width: 125mm; }}
.badge {{ display: inline-block; padding: 1.2mm 2.6mm; border: 0.6pt solid {HAIRLINE}; border-radius: 2pt; font-size: 6.8pt; letter-spacing: 0.1em; text-transform: uppercase; color: {INK_SOFT}; white-space: nowrap; }}
.meta {{ margin: 7mm 0 0; border-top: 0.6pt solid {HAIRLINE}; border-bottom: 0.6pt solid {HAIRLINE}; }}
.meta td {{ width: 25%; padding: 3mm 4mm 3mm 0; vertical-align: top; }}
.meta td + td {{ padding-left: 4mm; border-left: 0.6pt solid {HAIRLINE_SOFT}; }}
.meta__label {{ display: block; font-size: 6.5pt; letter-spacing: 0.12em; text-transform: uppercase; color: {MUTED}; }}
.meta__value {{ display: block; margin-top: 1mm; font-size: 9.2pt; }}
.section-head {{ width: 100%; border-collapse: collapse; margin: 9mm 0 2.5mm; }}
.section-head td {{ padding: 0; border: 0; vertical-align: baseline; }}
.section-head__count {{ text-align: right; white-space: nowrap; font-size: 7.2pt; color: {MUTED}; }}
.section-head h2 {{ margin: 0; font-size: 7.2pt; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: {INK_SOFT}; }}
.data {{ width: 100%; border-collapse: collapse; }}
.data thead th {{ padding: 2.2mm 2mm; border-bottom: 0.9pt solid {INK}; font-size: 6.8pt; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: {MUTED}; text-align: left; }}
.data tbody td {{ padding: 2.4mm 2mm; font-size: 8.6pt; vertical-align: top; }}
.data tbody tr:nth-child(even) td {{ background: {ZEBRA}; }}
.data tr {{ page-break-inside: avoid; }}
.data--fixed {{ table-layout: auto; }}
.data--fixed thead th {{ white-space: nowrap; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.state {{ white-space: nowrap; }}
.dot {{ display: inline-block; width: 3.6pt; height: 3.6pt; margin-right: 1.6mm; border-radius: 50%; background: {FAINT}; vertical-align: 0.4pt; }}
.dot--nuevo {{ background: {ACCENT}; }}
.dot--confirmado {{ background: #75bda3; }}
.dot--entregado {{ background: #29664f; }}
.dot--cancelado {{ background: {FAINT}; }}
.empty td {{ padding: 14mm 2mm; text-align: center; color: {MUTED}; font-size: 8.6pt; }}
.totals {{ width: 76mm; margin: 8mm 0 0 auto; border-collapse: collapse; page-break-inside: avoid; }}
.totals td, .totals th {{ padding: 1.9mm 0; border: 0; background: none; }}
.totals th {{ font-size: 7.6pt; font-weight: 400; letter-spacing: 0.02em; color: {MUTED}; text-align: left; }}
.totals td {{ font-size: 8.8pt; text-align: right; font-variant-numeric: tabular-nums; }}
.totals tr + tr td, .totals tr + tr th {{ border-top: 0.5pt solid {HAIRLINE_SOFT}; }}
.totals tr.grand th {{ padding-top: 3mm; border-top: 0.9pt solid {INK}; font-size: 7.6pt; letter-spacing: 0.12em; text-transform: uppercase; color: {INK_SOFT}; }}
.totals tr.grand td {{ padding-top: 2.4mm; border-top: 0.9pt solid {INK}; font-family: {SERIF}; font-size: 13pt; }}
.notes {{ margin: 9mm 0 0; padding-top: 3.5mm; border-top: 0.6pt solid {HAIRLINE}; max-width: 135mm; font-size: 7.1pt; line-height: 1.55; color: {MUTED}; }}
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _css_text(value: str) -> str:
    return _esc(value).replace("\\", "\\\\")


def _page_css(running_title: str, running_left: str) -> str:
    return (
        "@page {\n"
        "  size: A4;\n"
        "  margin: 20mm 15mm 20mm 15mm;\n"
        f'  @top-right {{ content: "{_css_text(running_title)}"; font-family: {SANS};'
        " font-size: 6.6pt; letter-spacing: 0.12em; text-transform: uppercase;"
        f" color: {FAINT}; }}\n"
        f'  @bottom-left {{ content: "{_css_text(running_left)}"; font-family: {SANS};'
        f" font-size: 6.8pt; color: {MUTED}; }}\n"
        '  @bottom-right { content: "Página " counter(page) " de " counter(pages);'
        f" font-family: {SANS}; font-size: 6.8pt; color: {MUTED}; }}\n"
        "}\n"
        "@page :first { @top-right { content: none; } }\n"
    )


def _meta_html(meta: Sequence[tuple[str, str]]) -> str:
    if not meta:
        return ""
    width = f"{100 / len(meta):.4f}%"
    cells = "".join(
        f'<td style="width: {width}"><span class="meta__label">{_esc(label)}</span>'
        f'<span class="meta__value">{_esc(value)}</span></td>'
        for label, value in meta
    )
    return f'<table class="band meta"><tr>{cells}</tr></table>'


def _cell_html(value: object, index: int, numeric_columns: set[int], pill_columns: set[int]) -> str:
    classes = []
    if index in numeric_columns:
        classes.append("num")
    inner = _esc(value)
    if index in pill_columns and str(value).strip():
        state = str(value).strip().lower()
        inner = (
            f'<span class="state"><span class="dot dot--{_esc(state)}"></span>'
            f"{_esc(str(value).strip().capitalize())}</span>"
        )
    attr = f' class="{" ".join(classes)}"' if classes else ""
    return f"<td{attr}>{inner}</td>"


def _table_html(
    columns: Sequence[str],
    rows: Sequence[Sequence[object]],
    numeric_columns: set[int],
    pill_columns: set[int],
    empty_message: str,
    column_widths: Sequence[str] = (),
) -> str:
    head = "".join(
        f'<th class="num">{_esc(c)}</th>' if i in numeric_columns else f"<th>{_esc(c)}</th>"
        for i, c in enumerate(columns)
    )
    if rows:
        body = ""
        for row in rows:
            cells = [
                _cell_html(row[i] if i < len(row) else "", i, numeric_columns, pill_columns)
                for i in range(len(columns))
            ]
            body += "<tr>" + "".join(cells) + "</tr>"
    else:
        body = f'<tr class="empty"><td colspan="{len(columns)}">{_esc(empty_message)}</td></tr>'
    fixed = ' class="data data--fixed"' if column_widths else ' class="data"'
    cols = ""
    if column_widths:
        cols = "<colgroup>" + "".join(
            f'<col style="width: {_esc(w)}">' for w in column_widths
        ) + "</colgroup>"
    return (
        f"<table{fixed}>{cols}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def _totals_html(totals: Sequence[tuple[str, str]]) -> str:
    if not totals:
        return ""
    rows = ""
    last = len(totals) - 1
    for i, (label, value) in enumerate(totals):
        klass = ' class="grand"' if i == last else ""
        rows += f"<tr{klass}><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>"
    return f'<table class="totals"><tbody>{rows}</tbody></table>'


def render_document_html(
    title: str,
    subtitle: str = "",
    business_name: str = "",
    footer_text: str = "",
    document_kind: str = "Documento de gestión",
    badge: str = "",
    meta: Sequence[tuple[str, str]] = (),
    columns: Sequence[str] = (),
    rows: Sequence[Sequence[object]] = (),
    numeric_columns: Sequence[int] = (),
    pill_columns: Sequence[int] = (),
    totals: Sequence[tuple[str, str]] = (),
    section_title: str = "Detalle",
    empty_message: str = "Sin registros en el período.",
    column_widths: Sequence[str] = (),
    generated_at: datetime.datetime | None = None,
) -> str:
    if not columns:
        raise ValueError("columns no puede estar vacio")

    stamp = generated_at or datetime.datetime.now()
    brand = business_name.strip() or "Toscana Pastry"
    count = f"{len(rows)} {'registro' if len(rows) == 1 else 'registros'}"
    badge_html = f'<span class="badge">{_esc(badge)}</span>' if badge else ""
    subtitle_html = f'<p class="subtitle">{_esc(subtitle)}</p>' if subtitle else ""
    notes_html = f'<p class="notes">{_esc(footer_text)}</p>' if footer_text.strip() else ""

    masthead = (
        '<table class="band masthead"><tr>'
        '<td class="masthead__keep">'
        f'<span class="brand__name">{_esc(brand)}</span>'
        f'<span class="brand__kind">{_esc(document_kind)}</span></td>'
        '<td class="masthead__right">'
        f'<span class="masthead__label">{stamp.strftime("%d/%m/%Y")}</span>'
        f'<span class="masthead__stamp">{stamp.strftime("%H:%M")} h</span></td>'
        "</tr></table>"
    )
    title_block = (
        '<table class="band title-block"><tr>'
        f'<td class="title-block__keep"><h1>{_esc(title)}</h1>{subtitle_html}</td>'
        f'<td>{badge_html}</td>'
        "</tr></table>"
    )
    section_head = (
        '<table class="section-head"><tr>'
        f'<td><h2>{_esc(section_title)}</h2></td>'
        f'<td class="section-head__count">{_esc(count)}</td>'
        "</tr></table>"
    )

    body = (
        f"{masthead}"
        '<div class="rule"></div>'
        f"{title_block}"
        f"{_meta_html(meta)}"
        f"{section_head}"
        f"{_table_html(columns, rows, set(numeric_columns), set(pill_columns), empty_message, column_widths)}"
        f"{_totals_html(totals if rows else ())}"
        f"{notes_html}"
    )

    return (
        '<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
        f"<style>{_page_css(title, brand)}{_BASE_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


def render_document_pdf(
    title: str,
    subtitle: str = "",
    business_name: str = "",
    footer_text: str = "",
    document_kind: str = "Documento de gestión",
    badge: str = "",
    meta: Sequence[tuple[str, str]] = (),
    columns: Sequence[str] = (),
    rows: Sequence[Sequence[object]] = (),
    numeric_columns: Sequence[int] = (),
    pill_columns: Sequence[int] = (),
    totals: Sequence[tuple[str, str]] = (),
    section_title: str = "Detalle",
    empty_message: str = "Sin registros en el período.",
    column_widths: Sequence[str] = (),
    generated_at: datetime.datetime | None = None,
) -> bytes:
    from weasyprint import HTML

    return HTML(
        string=render_document_html(
            title=title,
            subtitle=subtitle,
            business_name=business_name,
            footer_text=footer_text,
            document_kind=document_kind,
            badge=badge,
            meta=meta,
            columns=columns,
            rows=rows,
            numeric_columns=numeric_columns,
            pill_columns=pill_columns,
            totals=totals,
            section_title=section_title,
            empty_message=empty_message,
            column_widths=column_widths,
            generated_at=generated_at,
        )
    ).render().write_pdf()
