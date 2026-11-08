"""Plegado de acentos y mayúsculas para búsqueda (RF-P2-02).

Se registra como función SQL `accent_fold` en SQLite: el repositorio la
usa vía `func.accent_fold(IngredientORM.name)` para que "cafe" encuentre
"Café". En Postgres la spec manda pg_trgm/GIN (tarea de despliegue); esta
función cubre el desarrollo en SQLite sin cambiar el repositorio.
"""
import unicodedata


def accent_fold(s: str) -> str:
    """NFD, descarta marcas de combinación y minúsculas: 'Café' -> 'cafe'.

    SQLite evalua la funcion UDF sobre filas NULL (p. ej. sku nullable)
    antes de filtrar con IS NOT NULL: None -> None (SQL NULL) para que
    la comparacion no lance TypeError y no coincida con nada.
    """
    if s is None:
        return None
    return "".join(
        char
        for char in unicodedata.normalize("NFD", s)
        if unicodedata.category(char) != "Mn"
    ).lower()


SEARCH_MAX_LENGTH = 120
"""Longitud máxima del término de búsqueda (espejo de Query(max_length) en la API)."""


class SearchQueryError(ValueError):
    """Término de búsqueda inválido; la API debe responder 422."""


def validate_search_term(q: str) -> str:
    """Valida un término de búsqueda y devuelve el valor limpio (strip).

    Reglas estrictas (la búsqueda se trata SOLO como datos inermes):
    - vacío o solo espacios → SearchQueryError.
    - cualquier carácter de categoría "C" de Unicode (control, formato/bidi,
      surrogate, uso privado, no asignado) → SearchQueryError: invisibles y
      controles de dirección (p. ej. U+202E) son vector de poisoning de
      logs/URLs, no son texto buscable.
    - más de ``SEARCH_MAX_LENGTH`` caracteres → SearchQueryError.

    Lo que esto NO valida: metacaracteres de LIKE (`%`, `_`, `\\`); esos se
    escapan en :func:`build_search_pattern`, no se rechazan (el usuario
    puede buscar "50% off" literal).
    """
    stripped = q.strip()
    if not stripped:
        raise SearchQueryError("q must not be empty")
    if any(unicodedata.category(ch).startswith("C") for ch in stripped):
        raise SearchQueryError("q contains invalid characters")
    if len(stripped) > SEARCH_MAX_LENGTH:
        raise SearchQueryError(f"q must be at most {SEARCH_MAX_LENGTH} characters")
    return stripped


def escape_like(s: str) -> str:
    """Escapa metacaracteres de LIKE: la búsqueda queda siempre como
    substring literal.

    Sin esto, `?q=%` coincidiría con todo y `?q=a_b` interpretaría el `_`
    del usuario como "cualquier carácter" (wildcard injection).
    """
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_search_pattern(q: str) -> str:
    """Patern LIKE para ``q``: valida → pliega acentos → escapa → ``%…%``.

    El repositorio debe invocarlo con ``.like(pattern, escape="\\")`` para
    que SQLite y Postgres respeten la barra invertida de escape. El valor
    viaja como parámetro bind (nunca concatenado al texto SQL).
    """
    folded = accent_fold(validate_search_term(q))
    return f"%{escape_like(folded)}%"
