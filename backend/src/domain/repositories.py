from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Tuple
from datetime import datetime, date
from decimal import Decimal
from domain.customer_address import CustomerAddress
from domain.models import User, UserRole, BusinessSettings, Ingredient, Product, StockMovement, StockStatus
from domain.orders import Customer, Order
from domain.budgets import Budget
from domain.imports import ImportRow, ImportSession

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


class RefreshTokenRepository(ABC):
    """Server-side record of issued refresh tokens (rotation + revocation)."""

    @abstractmethod
    async def add(
        self, jti: str, user_id: str, family_id: str, expires_at: datetime
    ) -> None:
        pass

    @abstractmethod
    async def consume(self, jti: str) -> bool:
        """Atomically mark the token as used. False when it is unknown,
        already used/revoked or expired."""
        pass

    @abstractmethod
    async def revoke_family(self, family_id: str) -> None:
        pass


class SettingsRepository(ABC):
    @abstractmethod
    async def get(self) -> Optional[BusinessSettings]:
        pass

    @abstractmethod
    async def save(self, settings: BusinessSettings) -> BusinessSettings:
        pass


class IngredientRepository(ABC):

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
    async def get_many(self, ingredient_ids: Sequence[str]) -> List[Ingredient]:
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
        pass

    @abstractmethod
    async def list_by_user(self, user_id: str) -> List[CustomerAddress]:
        pass

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

class ProductRepository(ABC):

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


class CustomerRepository(ABC):

    @abstractmethod
    async def list(
        self,
        q: Optional[str],
        page: int,
        page_size: int,
    ) -> tuple[List["Customer"], int]:
        pass

    @abstractmethod
    async def get(self, customer_id: str) -> Optional["Customer"]:
        pass

    @abstractmethod
    async def update_address(
        self, customer_id: str, delivery_address: Optional[str]
    ) -> Optional["Customer"]:
        pass

    @abstractmethod
    async def get_or_create(
        self, customer: "Customer"
    ) -> tuple["Customer", bool]:
        pass


class OrderRepository(ABC):

    @abstractmethod
    async def list_orders(
        self,
        status: Optional[str],
        customer_id: Optional[str],
        q: Optional[str],
        date_from: Optional[date],
        date_to: Optional[date],
        page: int,
        page_size: int,
        paid: Optional[bool] = None,
    ) -> tuple[List["Order"], int]:
        pass

    @abstractmethod
    async def get_full(self, order_id: str) -> Optional["Order"]:
        pass

    @abstractmethod
    async def create_full(self, order: "Order") -> "Order":
        pass

    @abstractmethod
    async def update_full(self, order: "Order") -> Optional["Order"]:
        pass

    @abstractmethod
    async def mark_whatsapp_sent(
        self, order: "Order", sent_at: datetime
    ) -> None:
        pass


class BudgetRepository(ABC):

    @abstractmethod
    async def list(
        self,
        status: Optional[str],
        q: Optional[str],
        date_from: Optional[date],
        date_to: Optional[date],
        page: int,
        page_size: int,
    ) -> tuple[List["Budget"], int]:
        pass

    @abstractmethod
    async def get(self, budget_id: str) -> Optional["Budget"]:
        pass

    @abstractmethod
    async def create(self, budget: "Budget") -> "Budget":
        pass

    @abstractmethod
    async def update(self, budget: "Budget") -> Optional["Budget"]:
        pass

    @abstractmethod
    async def delete(self, budget_id: str) -> bool:
        pass

    @abstractmethod
    async def mark_converted(self, budget_id: str, order_id: str) -> bool:
        pass

    @abstractmethod
    async def mark_sent(self, budget: "Budget") -> "Budget":
        pass

class OrderTransitionStore(ABC):

    @abstractmethod
    async def lock_order(self, order_id: str) -> Optional["Order"]:
        pass

    @abstractmethod
    async def lock_ingredients(
        self, ingredient_ids: List[str]
    ) -> Dict[str, Ingredient]:
        pass

    @abstractmethod
    async def apply_movements(
        self, changes: List[Tuple[Ingredient, StockMovement]]
    ) -> None:
        pass

    @abstractmethod
    async def set_status(self, order_id: str, status: str) -> None:
        pass

    @abstractmethod
    async def commit(self) -> None:
        pass

    @abstractmethod
    async def rollback(self) -> None:
        pass


    @abstractmethod
    async def record_whatsapp_sent_within_limit(
        self, budget_id: str, masked_phone: str, since: datetime, limit: int
    ) -> Optional[datetime]:
        pass


class DocumentRepository(ABC):

    @abstractmethod
    async def get(self, budget_id: str, content_hash: str) -> Optional[bytes]:
        pass

    @abstractmethod
    async def save(self, budget_id: str, content_hash: str, pdf: bytes) -> None:
        pass


class ImportRepository(ABC):

    @abstractmethod
    async def create_session(self, session: ImportSession) -> ImportSession:
        pass

    @abstractmethod
    async def bulk_insert_rows(
        self, import_id: str, tenant_id: str, rows: Sequence[ImportRow]
    ) -> int:
        pass

    @abstractmethod
    async def get_session(
        self, import_id: str, tenant_id: str
    ) -> Optional[ImportSession]:
        pass

    @abstractmethod
    async def list_rows(
        self,
        import_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[ImportRow], int]:
        pass

    @abstractmethod
    async def set_status(
        self,
        import_id: str,
        status: str,
        confirmed_at: Optional[datetime] = None,
    ) -> None:
        pass

    @abstractmethod
    async def delete_staging_rows(self, import_id: str) -> int:
        pass

    @abstractmethod
    async def purge_expired(self, now: datetime) -> int:
        pass
