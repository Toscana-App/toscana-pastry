from abc import ABC, abstractmethod
from typing import Optional, List
from decimal import Decimal
from domain.models import User, UserRole, BusinessSettings, Ingredient, Product, StockMovement, StockStatus

class UserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def save(self, user: User) -> User:
        pass

    @abstractmethod
    async def get_all_by_role(self, role: UserRole) -> List[User]:
        pass

    @abstractmethod
    async def get_all(self) -> List[User]:
        pass


class SettingsRepository(ABC):
    @abstractmethod
    async def get(self) -> Optional[BusinessSettings]:
        pass

    @abstractmethod
    async def save(self, settings: BusinessSettings) -> BusinessSettings:
        pass


class IngredientRepository(ABC):
    """P2 ingredientes. Borrado suave: lo eliminado queda en la tabla pero
    es invisible a list/get; `count_active_recipes` alimenta el 409 de UC-05."""

    @abstractmethod
    async def list(
        self,
        q: Optional[str],
        status: Optional[StockStatus],
        page: int,
        page_size: int,
    ) -> tuple[List[Ingredient], int]:
        pass

    @abstractmethod
    async def get(self, ingredient_id: str) -> Optional[Ingredient]:
        pass

    @abstractmethod
    async def create(
        self,
        ingredient: Ingredient,
        initial_movement: Optional[StockMovement] = None,
    ) -> Ingredient:
        pass

    @abstractmethod
    async def update(self, ingredient: Ingredient) -> Optional[Ingredient]:
        pass

    @abstractmethod
    async def soft_delete(self, ingredient_id: str) -> Optional[Ingredient]:
        pass

    @abstractmethod
    async def count_active_recipes(self, ingredient_id: str) -> int:
        pass

    @abstractmethod
    async def add_movement(
        self,
        ingredient_id: str,
        movement: StockMovement,
        new_stock_qty: Decimal,
    ) -> Optional[StockMovement]:
        pass

    @abstractmethod
    async def list_movements(
        self, ingredient_id: str, page: int, page_size: int
    ) -> tuple[List[StockMovement], int]:
        pass


class ProductRepository(ABC):
    """P3/P4 productos. Borrado suave: lo eliminado queda en la tabla pero
    es invisible a list/get (UC-07). `count_orders` alimenta el 409 de
    UC-07 cuando existan pedidos (Fase 6); hasta entonces siempre 0,
    como `count_active_recipes` pre-Fase 5."""

    @abstractmethod
    async def list(
        self,
        q: Optional[str],
        category: Optional[str],
        page: int,
        page_size: int,
    ) -> tuple[List[Product], int]:
        pass

    @abstractmethod
    async def get(self, product_id: str) -> Optional[Product]:
        pass

    @abstractmethod
    async def create(self, product: Product) -> Product:
        pass

    @abstractmethod
    async def update(self, product: Product) -> Optional[Product]:
        pass

    @abstractmethod
    async def soft_delete(self, product_id: str) -> Optional[Product]:
        pass

    @abstractmethod
    async def count_orders(self, product_id: str) -> int:
        pass

    @abstractmethod
    async def distinct_categories(self) -> List[str]:
        pass
