from typing import Dict, List, Optional, Sequence

from domain.models import BusinessSettings, Ingredient, Product, RecipeItem
from domain.pricing import calculate_price


class ProductValidationError(ValueError):
    """La receta o los datos del producto violan una regla de dominio."""


class ProductPublishBlockedError(ValueError):
    def __init__(self, missing: List[str]):
        self.missing = missing
        super().__init__("producto incompleto: no se puede publicar")


def assemble_product(
    name: Optional[str],
    category: Optional[str],
    description: Optional[str],
    prep_time_min: Optional[int],
    servings: Optional[int],
    difficulty: Optional[str],
    recipe: Optional[Sequence[RecipeItem]],
    existing: Optional[Product],
    settings: BusinessSettings,
    ingredients_by_id: Dict[str, Ingredient],
    available: Optional[bool] = None,
    image_url: Optional[str] = None,
) -> Product:
    """Arma el Product de dominio y valida la receta contra los insumos
    corrientes. En create, los campos omitidos vienen de los default de
    settings (RF-P4-01). Lanza ProductValidationError."""
    if existing is None:
        name = name or ""
        category = category or ""
        description = description or ""
        prep_time_min = (
            settings.default_prep_minutes if prep_time_min is None else prep_time_min
        )
        servings = settings.default_servings if servings is None else servings
        difficulty = settings.default_difficulty if difficulty is None else difficulty
        available = False
        image_url = None
    else:
        name = name if name is not None else existing.name
        category = category if category is not None else existing.category
        description = description if description is not None else existing.description
        prep_time_min = (
            prep_time_min if prep_time_min is not None else existing.prep_time_min
        )
        servings = servings if servings is not None else existing.servings
        difficulty = difficulty if difficulty is not None else existing.difficulty
        available = available if available is not None else existing.available
        image_url = image_url if image_url is not None else existing.image_url

    if recipe is not None:
        recipe_items: List[RecipeItem] = list(recipe)
        line_items: List[tuple] = []
        for item in recipe_items:
            ingredient = ingredients_by_id.get(item.ingredient_id)
            if ingredient is None:
                raise ProductValidationError(
                    f"Insumo desconocido en la receta: {item.ingredient_id}"
                )
            line_items.append(
                (item.qty, item.unit, ingredient.price_per_unit, ingredient.unit)
            )
    else:
        # Receta sin cambios: se conserva. Lineas cuyo insumo fue borrado
        # no bloquean el guardado (el producto queda "incompleto" en
        # lectura; el detalle lo muestra).
        recipe_items = list(existing.recipe) if existing is not None else []
        line_items = [
            (
                item.qty,
                item.unit,
                ingredients_by_id[item.ingredient_id].price_per_unit,
                ingredients_by_id[item.ingredient_id].unit,
            )
            for item in recipe_items
            if item.ingredient_id in ingredients_by_id
        ]

    try:
        product = Product(
            name=name,
            category=category,
            recipe=tuple(recipe_items),
            description=description,
            prep_time_min=prep_time_min,
            servings=servings,
            difficulty=difficulty,
            available=available,
            image_url=image_url,
            **({"id": existing.id, "deleted_at": existing.deleted_at} if existing else {}),
        )
        # Validacion de unidades con el mismo codigo que /pricing/preview
        # (UnitConversionError hereda de ValueError).
        calculate_price(line_items, product.prep_time_min, settings.to_pricing())
    except ValueError as e:
        raise ProductValidationError(str(e)) from e
    return product
