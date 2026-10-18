from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from domain.models import User, UserRole, BusinessSettings, Ingredient, Product, StockMovement, StockStatus
from domain.orders import Customer, Order
from domain.budgets import Budget

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
    es invisible a list/get (UC-07). `count_orders` alimenta la respuesta
    de UC-07 cuando el producto tiene pedidos historicos (Fase 6)."""

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
    """P6 clientes. Dedup por (nombre normalizado, telefono normalizado):
    crear un duplicado devuelve el existente (RF-P6-08). Sin borrado:
    el historial de pedidos no se rompe."""

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
    async def get_or_create(
        self, customer: "Customer"
    ) -> tuple["Customer", bool]:
        """Devuelve (cliente, creado). Si ya existe (dedup), devuelve el
        existente con creado=False; si no, persiste el nuevo (creado=True)."""
        pass


class OrderRepository(ABC):
    """P6 pedidos. Los snapshots de items son inmutables (RNF-P6-03):
    solo se escriben en create. `confirm`/`cancel` gestionan stock y
    estado en una sola transaccion (RNF-P6-02/04)."""

    @abstractmethod
    async def list(
        self,
        status: Optional[str],
        customer_id: Optional[str],
        q: Optional[str],
        date_from: Optional[date],
        date_to: Optional[date],
        page: int,
        page_size: int,
    ) -> tuple[List["Order"], int]:
        pass

    @abstractmethod
    async def get(self, order_id: str) -> Optional["Order"]:
        pass

    @abstractmethod
    async def create(self, order: "Order") -> "Order":
        pass

    @abstractmethod
    async def update(self, order: "Order") -> Optional["Order"]:
        """Reemplaza lineas/snapshot en pedidos estado `nuevo` (el router
        valida el estado antes de llamar)."""
        pass

    @abstractmethod
    async def confirm(self, order: "Order") -> "Order":
        """nuevo -> confirmado con descuento de stock atómico. Levanta
        InsufficientOrderStockError (rollback total) si no alcanza."""
        pass

    @abstractmethod
    async def cancel(self, order: "Order") -> "Order":
        """confirmado -> cancelado con reposicion de stock."""
        pass

    @abstractmethod
    async def mark_delivered(self, order: "Order") -> "Order":
        """confirmado -> entregado. Sin efecto sobre stock."""
        pass

    @abstractmethod
    async def mark_whatsapp_sent(
        self, order: "Order", sent_at: datetime
    ) -> None:
        pass


class BudgetRepository(ABC):
    """P7/P8 presupuestos. Los items guardan costo/precio derivados
    contra el catalogo al momento de la escritura; las lecturas son puras.
    La secuencia `#000NN` se asigna en create (misma transaccion) y no se
    reusa tras borrado (RNF-P8-04). `mark_sent` congela un snapshot de
    version (RF-P8-05)."""

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
        """Asigna la secuencia del tenant en la misma transaccion."""
        pass

    @abstractmethod
    async def update(self, budget: "Budget") -> Optional["Budget"]:
        """Reemplaza items/parametros. Conserva seq/status/version.
        El estado lo valida el router antes de llamar."""
        pass

    @abstractmethod
    async def delete(self, budget_id: str) -> bool:
        """Borrado duro: no tiene efecto sobre stock ni secuencia."""
        pass

    @abstractmethod
    async def mark_sent(self, budget: "Budget") -> "Budget":
        """enviado (version nueva) con snapshot congelado (RF-P8-05).
        `budget` ya pasa por transition_to_sent."""
        pass
