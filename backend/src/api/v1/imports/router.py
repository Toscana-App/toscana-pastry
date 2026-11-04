"""API de importacion CSV con staging (T-CSV-2/3/4).

Endpoints:
- GET  /imports/template?entity=   plantilla CSV (mismo modelo que valida).
- POST /imports                    subir (multipart): valida columnas E datos,
                                   estadia. 422 si el set de columnas no coincide
                                   (SIN crear import_id ni staging) o si hay
                                   columnas ajenas/faltantes.
- GET  /imports/{id}/rows          preview de filas (paginado, filtro por estado).
- POST /imports/{id}/confirm       transaccion unica: inserta validas,
                                   duplicados → skipped. 409 si ya confirmada.
- DELETE /imports/{id}             descarta (borra staging). 409 si confirmada.

Solo ADMIN (RNF-CSV-08). El tenant de la app es monotenante: se guarda
``tenant_id = user_id`` (el owner) para aislar las importaciones por usuario.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, status, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.dependencies import require_admin
from api.v1.imports.adapters.base import ImportAdapter
from api.v1.imports.dependencies import resolve_adapter
from api.v1.imports.parsers import (
    decode_text,
    detect_delimiter,
    parse_csv,
    rows_to_dicts,
)
from api.v1.imports.schemas import (
    ConfirmResponse,
    DiscardResponse,
    ImportRowOut,
    ImportRowsResponse,
    ImportSessionOut,
    ImportUploadResponse,
)
from data.db import get_db
from data.repositories.sql_import_repository import SQLImportRepository
from domain.imports import (
    ColumnMismatchError,
    ImportRow,
    ImportRowStatus,
    ImportSession,
    ImportStatus,
    check_columns,
)
from domain.models import User

router = APIRouter(prefix="/imports", tags=["imports"])

MAX_FILE_BYTES = 5 * 1024 * 1024  # RNF-CSV-03
MAX_ROWS = 10_000  # RNF-CSV-03
FIRST_ERRORS_LIMIT = 10


def _mismatch_detail(exc: ColumnMismatchError) -> dict:
    return {
        "message": "El archivo no coincide con la plantilla de columnas.",
        "missing": exc.missing,
        "extra": exc.extra,
    }


@router.get("/template")
async def get_template(
    entity: str = Query(...),
    current_user: User = Depends(require_admin),
) -> PlainTextResponse:
    """Plantilla CSV de la entidad (RF-CSV-01). Descarga directa."""
    adapter = resolve_adapter(entity)
    return PlainTextResponse(
        adapter.template(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{entity}_plantilla.csv"'
        },
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    entity: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ImportUploadResponse:
    adapter: ImportAdapter = resolve_adapter(entity)
    raw = await file.read()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo supera 5 MB; dividilo en lotes más chicos.",
        )
    if not raw:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El archivo está vacío."
        )

    text, encoding = decode_text(raw)
    delimiter = detect_delimiter(text)
    headers, raw_rows = parse_csv(text, delimiter)

    # Validación estricta de columnas ANTES de crear import_id ni staging
    # (RF-CSV-02/13): set exacto, orden irrelevante.
    try:
        check_columns(adapter.columns, headers)
    except ColumnMismatchError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_mismatch_detail(exc)
        )

    if len(raw_rows) > MAX_ROWS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El archivo tiene más de {MAX_ROWS} filas; dividilo en lotes.",
        )

    row_dicts = rows_to_dicts(headers, raw_rows)
    parsed: list[ImportRow] = []
    for index, row in enumerate(row_dicts, start=1):
        data, errors = adapter.validate_row(row)
        parsed.append(
            ImportRow(
                row_number=index,
                status=ImportRowStatus.INVALID if errors else ImportRowStatus.VALID,
                data=data,
                errors=errors,
            )
        )

    valid_rows = sum(
        1 for row in parsed if row.status == ImportRowStatus.VALID
    )
    owner = current_user.id
    session = ImportSession.create(
        tenant_id=owner,
        user_id=owner,
        entity=entity,
        filename=file.filename or f"{entity}.csv",
        delimiter=delimiter,
        encoding=encoding,
        template_columns=list(adapter.columns),
        total_rows=len(raw_rows),
        valid_rows=valid_rows,
    )

    repo = SQLImportRepository(db)
    await repo.create_session(session)
    await repo.bulk_insert_rows(session.id, owner, parsed)

    first_errors = [
        list(row.errors)
        for row in parsed
        if row.status == ImportRowStatus.INVALID
    ][:FIRST_ERRORS_LIMIT]
    return ImportUploadResponse(
        import_id=session.id,
        entity=entity,
        total_rows=session.total_rows,
        valid_rows=session.valid_rows,
        invalid_rows=session.invalid_rows,
        first_errors=first_errors,
    )


@router.get("/{import_id}/rows")
async def get_rows(
    import_id: str,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ImportRowsResponse:
    if status_filter is not None and status_filter not in ("valid", "invalid"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filtro inválido: usá 'valid' o 'invalid'.",
        )
    repo = SQLImportRepository(db)
    session = await repo.get_session(import_id, current_user.id)
    if session is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="La importación no existe."
        )
    row_objs, total = await repo.list_rows(
        import_id, status=status_filter, page=page, page_size=page_size
    )
    return ImportRowsResponse(
        session=ImportSessionOut(
            import_id=session.id,
            entity=session.entity,
            status=session.status.value,
            filename=session.filename,
            delimiter=session.delimiter,
            encoding=session.encoding,
            template_columns=session.template_columns,
            total_rows=session.total_rows,
            valid_rows=session.valid_rows,
            invalid_rows=session.invalid_rows,
            created_at=session.created_at,
            confirmed_at=session.confirmed_at,
        ),
        rows=[
            ImportRowOut(
                row_number=row.row_number,
                status=row.status.value,
                data=dict(row.data),
                errors=list(row.errors),
            )
            for row in row_objs
        ],
        total=total,
    )


@router.post("/{import_id}/confirm")
async def confirm(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ConfirmResponse:
    repo = SQLImportRepository(db)
    session = await repo.get_session(import_id, current_user.id)
    if session is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="La importación no existe."
        )
    if session.status == ImportStatus.CONFIRMED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="La importación ya fue confirmada."
        )
    if session.status == ImportStatus.DISCARDED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="La importación fue descartada."
        )

    adapter = resolve_adapter(session.entity)
    row_objs, _ = await repo.list_rows(
        import_id, status=ImportRowStatus.VALID.value, page=1, page_size=MAX_ROWS
    )

    created = 0
    skipped = 0
    message = ""
    if adapter.inserts_on_confirm:
        for row in row_objs:
            data = dict(row.data)
            existing = await adapter.find_duplicate(db, data)
            if existing is not None:
                skipped += 1
            else:
                await adapter.insert(db, data)
                created += 1
    else:
        message = adapter.confirm_message

    # Transaccion unica (RNF-CSV-05): los inserts quedaron pendientes (flush
    # implicitos dentro de la misma transaccion); set_status y
    # delete_staging_rows NO commitan; el commit final es unico. Un error antes
    # de aca deja el cierre de sesion en rollback (get_db).
    await repo.set_status(
        import_id, ImportStatus.CONFIRMED.value, confirmed_at=datetime.now(UTC)
    )
    await repo.delete_staging_rows(import_id)
    await db.commit()

    return ConfirmResponse(
        import_id=import_id,
        status=ImportStatus.CONFIRMED.value,
        created=created,
        skipped=skipped,
        message=message,
    )


@router.delete("/{import_id}")
async def discard(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DiscardResponse:
    repo = SQLImportRepository(db)
    session = await repo.get_session(import_id, current_user.id)
    if session is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="La importación no existe."
        )
    if session.status == ImportStatus.CONFIRMED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="No se puede descartar una importación ya confirmada.",
        )
    await repo.set_status(import_id, ImportStatus.DISCARDED.value)
    await repo.delete_staging_rows(import_id)
    await db.commit()
    return DiscardResponse(
        import_id=import_id, status=ImportStatus.DISCARDED.value
    )
