from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Tuple
from datetime import datetime, date
from decimal import Decimal
from domain.customer_address import CustomerAddress
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
    async def list_orders(
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
    async def get_full(self, order_id: str) -> Optional["Order"]:
        pass

    @abstractmethod
    async def create_full(self, order: "Order") -> "Order":
        pass

    @abstractmethod
    async def update_full(self, order: "Order") -> Optional["Order"]:
        """Reemplaza lineas/snapshot en pedidos estado `nuevo` (el router
        valida el estado antes de llamar)."""
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
    async def mark_converted(self, budget_id: str, order_id: str) -> bool:
        """Persiste el pedido asociado solo si aun no hay uno (RF-P8-08).
        False = ya convertido o inexistente."""
        pass

    @abstractmethod
    async def mark_sent(self, budget: "Budget") -> "Budget":
        """enviado (version nueva) con snapshot congelado (RF-P8-05).
        `budget` ya pasa por transition_to_sent."""

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

    # -------------------------------------------------------------- WhatsApp

    @abstractmethod
    async def record_whatsapp_sent_within_limit(
        self, budget_id: str, masked_phone: str, since: datetime, limit: int
    ) -> Optional[datetime]:
        """Conteo + registro ATÓMICOS (un solo INSERT ... SELECT): None
        si ya hay `limit` envíos desde `since` (RF-P10-06). El teléfono
        se almacena ENMASCARADO (RNF-P10-05)."""
        pass


class DocumentRepository(ABC):
    """P9 (Fase 8): PDFs de presupuesto generados.

    Clave: (budget_id, content_hash). Presupuesto editado → hash nuevo →
    el documento se regenera (invalidación de cache por edición, P9).
    """

    @abstractmethod
    async def get(self, budget_id: str, content_hash: str) -> Optional[bytes]:
        pass

    @abstractmethod
    async def save(self, budget_id: str, content_hash: str, pdf: bytes) -> None:
        pass
