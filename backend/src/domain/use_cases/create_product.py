from typing import Optional, Sequence

from domain.models import Product, RecipeItem
from domain.repositories import (
    IngredientRepository,
    ProductRepository,
    SettingsRepository,
)
from domain.use_cases.get_settings import GetSettings
from domain.use_cases.product_assembly import assemble_product


class CreateProduct:

    def __init__(
        self,
        products: ProductRepository,
        ingredients: IngredientRepository,
        settings: SettingsRepository,
    ):
        self._products = products
        self._ingredients = ingredients
        self._settings = settings

    async def execute(
        self,
        name: str,
        category: str,
        recipe: Sequence[RecipeItem],
        description: Optional[str] = None,
        prep_time_min: Optional[int] = None,
        servings: Optional[int] = None,
        difficulty: Optional[str] = None,
    ) -> Product:
        settings = await GetSettings(self._settings).execute()
        ingredients = await self._ingredients.get_many(
            [item.ingredient_id for item in recipe]
        )
        product = assemble_product(
            name=name,
            category=category,
            description=description,
            prep_time_min=prep_time_min,
            servings=servings,
            difficulty=difficulty,
            recipe=recipe,
            existing=None,
            settings=settings,
            ingredients_by_id={i.id: i for i in ingredients},
        )
        await self._products.create(product)
        return product
