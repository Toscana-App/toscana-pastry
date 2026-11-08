from typing import Optional, Sequence

from domain.models import Product, RecipeItem
from domain.repositories import (
    IngredientRepository,
    ProductRepository,
    SettingsRepository,
)
from domain.product_price import derive_product_price
from domain.use_cases.get_settings import GetSettings
from domain.use_cases.product_assembly import (
    ProductPublishBlockedError,
    assemble_product,
)


class UpdateProduct:

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
        product_id: str,
        name: Optional[str] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        prep_time_min: Optional[int] = None,
        servings: Optional[int] = None,
        difficulty: Optional[str] = None,
        recipe: Optional[Sequence[RecipeItem]] = None,
        available: Optional[bool] = None,
    ) -> Optional[Product]:
        existing = await self._products.get(product_id)
        if existing is None:
            return None
        settings = await GetSettings(self._settings).execute()
        items = recipe if recipe is not None else existing.recipe
        ingredients = await self._ingredients.get_many(
            [item.ingredient_id for item in items]
        )
        product = assemble_product(
            name=name,
            category=category,
            description=description,
            prep_time_min=prep_time_min,
            servings=servings,
            difficulty=difficulty,
            recipe=recipe,
            existing=existing,
            settings=settings,
            ingredients_by_id={i.id: i for i in ingredients},
            available=available,
        )
        if available is True:
            price = derive_product_price(product, {i.id: i for i in ingredients}, settings)
            if not price.complete:
                raise ProductPublishBlockedError(list(price.missing))
        return await self._products.update(product)
