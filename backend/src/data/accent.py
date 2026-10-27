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
