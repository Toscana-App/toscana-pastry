"""Adapters de importacion por entidad (insumos, productos, clientes)."""
from api.v1.imports.adapters.base import ImportAdapter
from api.v1.imports.adapters.customers_adapter import CustomersAdapter
from api.v1.imports.adapters.ingredients_adapter import IngredientsAdapter
from api.v1.imports.adapters.products_adapter import ProductsAdapter

ADAPTERS: dict[str, ImportAdapter] = {
    IngredientsAdapter.entity: IngredientsAdapter(),
    ProductsAdapter.entity: ProductsAdapter(),
    CustomersAdapter.entity: CustomersAdapter(),
}

ENTITIES: list[str] = list(ADAPTERS.keys())

__all__ = [
    "ADAPTERS",
    "ENTITIES",
    "ImportAdapter",
    "IngredientsAdapter",
    "ProductsAdapter",
    "CustomersAdapter",
]
