from abc import ABC, abstractmethod
from typing import Optional, List
from decimal import Decimal
from domain.customer_address import CustomerAddress
from domain.models import User, UserRole, BusinessSettings, Ingredient, StockMovement, StockStatus

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


class CustomerAddressRepository(ABC):
    @abstractmethod
    async def lock_book(self, user_id: str) -> None:
        """Serializa escrituras concurrentes sobre el libro del usuario."""

    @abstractmethod
    async def list_by_user(self, user_id: str) -> List[CustomerAddress]:
        """Direcciones del usuario, de la mas antigua a la mas nueva."""

    @abstractmethod
    async def get_for_user(
        self, address_id: str, user_id: str
    ) -> Optional[CustomerAddress]:
        pass

    @abstractmethod
    async def insert(self, address: CustomerAddress, user_id: str) -> None:
        pass

    @abstractmethod
    async def set_fields(self, address: CustomerAddress, user_id: str) -> None:
        pass

    @abstractmethod
    async def set_default_flag(
        self, address_id: str, user_id: str, is_default: bool
    ) -> None:
        pass

    @abstractmethod
    async def remove(
        self, address_id: str, user_id: str
    ) -> Optional[CustomerAddress]:
        pass

    @abstractmethod
    async def commit(self) -> None:
        pass
