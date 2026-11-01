from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Tuple
from datetime import datetime, date
from decimal import Decimal
from domain.models import User, UserRole, BusinessSettings, Ingredient, Product, StockMovement, StockStatus
from domain.orders import Customer, Order

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
    async def get_many(self, ingredient_ids: Sequence[str]) -> List[Ingredient]:
        """Insumos activos cuyo id esta en `ingredient_ids` (una consulta)."""
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
    async def mark_whatsapp_sent(
        self, order: "Order", sent_at: datetime
    ) -> None:
        pass


class OrderTransitionStore(ABC):
    """Primitivas transaccionales para transicionar un pedido. No decide
    reglas de negocio: el caso de uso TransitionOrderStatus las orquesta.
    Orden de locks obligatorio: `lock_order` primero, `lock_ingredients`
    despues (ids ordenados) para evitar deadlocks."""

    @abstractmethod
    async def lock_order(self, order_id: str) -> Optional["Order"]:
        """Lockea el pedido y lo devuelve fresco desde la base (None si no
        existe). Abre la transaccion."""

    @abstractmethod
    async def lock_ingredients(
        self, ingredient_ids: List[str]
    ) -> Dict[str, Ingredient]:
        """Lockea los insumos existentes (no borrados), ordenados por id."""

    @abstractmethod
    async def apply_movements(
        self, changes: List[Tuple[Ingredient, StockMovement]]
    ) -> None:
        """Persiste el nuevo stock de cada insumo y su movimiento (sin commit)."""

    @abstractmethod
    async def set_status(self, order_id: str, status: str) -> None:
        """Cambia el estado del pedido lockeado (sin commit)."""

    @abstractmethod
    async def commit(self) -> None:
        pass

    @abstractmethod
    async def rollback(self) -> None:
        pass
