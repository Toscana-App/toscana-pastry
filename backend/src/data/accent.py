import unicodedata


def accent_fold(s: str) -> str:
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
    pass


def validate_search_term(q: str) -> str:
    stripped = q.strip()
    if not stripped:
        raise SearchQueryError("q must not be empty")
    if any(unicodedata.category(ch).startswith("C") for ch in stripped):
        raise SearchQueryError("q contains invalid characters")
    if len(stripped) > SEARCH_MAX_LENGTH:
        raise SearchQueryError(f"q must be at most {SEARCH_MAX_LENGTH} characters")
    return stripped


def escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_search_pattern(q: str) -> str:
    folded = accent_fold(validate_search_term(q))
    return f"%{escape_like(folded)}%"
