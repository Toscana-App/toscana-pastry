from sqlalchemy import Column, String, DateTime, Date, Integer, Boolean, Enum as SQLAlchemyEnum, ForeignKey, Text, LargeBinary
from sqlalchemy.orm import declarative_base, relationship
import datetime
import enum

Base = declarative_base()

class UserRoleEnum(str, enum.Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"

class UserORM(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    google_id = Column(String, unique=True, nullable=True)
    role = Column(SQLAlchemyEnum(UserRoleEnum), default=UserRoleEnum.CUSTOMER, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class BusinessSettingsORM(Base):
    """Parametros de precio. Un solo registro: la app es monotenante.

    Los montos se guardan como TEXT (no float): SQLite no tiene tipo decimal
    y convertir por float pierde precision, que en dinero no se tolera
    (RNF-P4-02). El dominio trabaja siempre con Decimal.
    """
    __tablename__ = "business_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    hourly_rate = Column(String, nullable=False)
    margin_pct = Column(String, nullable=False)
    round_step = Column(String, nullable=False)
    gas_pct = Column(String, default="0", nullable=False)
    waste_pct = Column(String, default="0", nullable=False)
    urgent_surcharge_pct = Column(String, default="20", nullable=False)
    include_labor = Column(Boolean, default=True, nullable=False)
    include_gas = Column(Boolean, default=False, nullable=False)
    include_waste = Column(Boolean, default=False, nullable=False)
    default_prep_minutes = Column(Integer, default=30, nullable=False)
    default_servings = Column(Integer, default=6, nullable=False)
    default_difficulty = Column(String, default="simple", nullable=False)
    # Fase 8 (P9): branding del PDF (solo texto; sin upload de logo en v1).
    business_name = Column(String, default="", nullable=False)
    footer_text = Column(String, default="", nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class IngredientORM(Base):
    """Insumo. Los montos/cantidades viajan como TEXT: SQLite no tiene tipo
    decimal y el float pierde precision que en dinero no se tolera (RNF-P4-02).
    `deleted_at` no nulo = soft delete (UC-05)."""

    __tablename__ = "ingredients"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    unit = Column(String, nullable=False)
    price_per_unit = Column(String, nullable=False)
    stock_qty = Column(String, nullable=False, default="0")
    low_stock_threshold = Column(String, nullable=False, default="0")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )


class StockMovementORM(Base):
    """Movimiento de stock. Historial inmutable: solo INSERT (RF-P2-04)."""

    __tablename__ = "stock_movements"
    id = Column(String, primary_key=True)
    ingredient_id = Column(
        String, ForeignKey("ingredients.id"), nullable=False, index=True
    )
    qty_delta = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    ref = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ProductORM(Base):
    """Producto de catalogo (Fase 5). Money/qty como TEXT (RNF-P4-02).
    deleted_at no nulo = borrado suave (UC-07)."""

    __tablename__ = "products"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    prep_time_min = Column(Integer, nullable=False, default=0)
    servings = Column(Integer, nullable=False, default=1)
    difficulty = Column(String, nullable=False, default="simple")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    recipe_items = relationship(
        "RecipeItemORM",
        cascade="all, delete-orphan",
        order_by="RecipeItemORM.position",
        lazy="selectin",
    )


class RecipeItemORM(Base):
    """Linea de receta: insumo + cantidad en su propia unidad. `position`
    conserva el orden que el usuario eligio."""

    __tablename__ = "recipe_items"
    id = Column(String, primary_key=True)
    product_id = Column(
        String, ForeignKey("products.id"), nullable=False, index=True
    )
    ingredient_id = Column(String, nullable=False, index=True)
    qty = Column(Text, nullable=False)
    unit = Column(String, nullable=False)
    position = Column(Integer, nullable=False, default=0)

# ---------------------------------------------------------------------------
# Fase 6 (P6): clientes y pedidos
# ---------------------------------------------------------------------------


class CustomerORM(Base):
    """Cliente del pedido (nombre + telefono). Dedup por (name_norm,
    phone_norm): mismo criterio de plegado que la busqueda con acentos
    (RF-P6-08). Sin borrado: el historial no se rompe."""

    __tablename__ = "customers"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=False)
    name_norm = Column(String, nullable=False, index=True)
    phone_norm = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        {"extend_existing": True},
    )


class OrderORM(Base):
    """Pedido. Money/qty como TEXT (RNF-P4-02). `margin_pct` nulo = default
    del tenant (el override se usa al congelar el snapshot). El desglose
    de cada item vive en OrderItemORM.snapshot (inmutable, RNF-P6-03)."""

    __tablename__ = "orders"
    id = Column(String, primary_key=True)
    customer_id = Column(
        String, ForeignKey("customers.id"), nullable=False, index=True
    )
    customer_name = Column(String, nullable=False, index=True)  # snapshot
    customer_phone = Column(String, nullable=False)  # snapshot
    date = Column("date", Date, nullable=False, index=True)
    status = Column(String, nullable=False, default="nuevo", index=True)
    margin_pct = Column(String, nullable=True)  # override; nulo = tenant
    whatsapp_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    items = relationship(
        "OrderItemORM",
        cascade="all, delete-orphan",
        order_by="OrderItemORM.position",
        lazy="selectin",
    )


class OrderItemORM(Base):
    """Linea de pedido con su snapshot congelado (JSON): cantidad escalada
    por porciones + desglose completo al momento del pedido (RNF-P6-03)."""

    __tablename__ = "order_items"
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=False)  # snapshot
    qty = Column(Integer, nullable=False)
    portions = Column(Integer, nullable=False)
    note = Column(Text, nullable=False, default="")
    position = Column(Integer, nullable=False, default=0)
    snapshot = Column(Text, nullable=False)  # JSON OrderItemSnapshot


class OrderEventORM(Base):
    """Evento audit del pedido (whatsapp, etc). Solo INSERT: historial."""

    __tablename__ = "order_events"
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Fase 7 (P7/P8): presupuestos
# ---------------------------------------------------------------------------


class TenantSequenceORM(Base):
    """Secuencia por tenant (monotenante: una sola fila por key).
    `current` crece en la misma transaccion que el presupuesto: sin reuso
    tras borrado (RNF-P8-04)."""

    __tablename__ = "tenant_sequences"
    key = Column(String, primary_key=True)
    current = Column(Integer, nullable=False, default=0)


class BudgetORM(Base):
    """Presupuesto. Money como TEXT (RNF-P4-02). `margin_pct` nulo =
    tenant (el override ya se aplico al derivar unit_selling de cada
    item: los totales se derivan en lectura, nunca se persisten)."""

    __tablename__ = "budgets"
    id = Column(String, primary_key=True)
    seq = Column(String, nullable=False, index=True)
    customer_id = Column(
        String, ForeignKey("customers.id"), nullable=False, index=True
    )
    customer_name = Column(String, nullable=False, index=True)  # snapshot
    customer_phone = Column(String, nullable=False)  # snapshot
    status = Column(String, nullable=False, default="borrador", index=True)
    calculation_mode = Column(String, nullable=False, default="cost_plus")
    margin_pct = Column(String, nullable=True)  # override; nulo = tenant
    version = Column(Integer, nullable=False, default=0)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    items = relationship(
        "BudgetItemORM",
        cascade="all, delete-orphan",
        order_by="BudgetItemORM.position",
        lazy="selectin",
    )


class BudgetItemORM(Base):
    """Linea de presupuesto con costo/precio derivados y congelados al
    momento de la escritura (la lectura no vuelve al catalogo)."""

    __tablename__ = "budget_items"
    id = Column(String, primary_key=True)
    budget_id = Column(String, ForeignKey("budgets.id"), nullable=False, index=True)
    product_id = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=False)  # snapshot
    qty = Column(Integer, nullable=False)
    unit_cost = Column(String, nullable=False)
    unit_selling = Column(String, nullable=False)
    price_overridden = Column(Boolean, nullable=False, default=False)
    position = Column(Integer, nullable=False, default=0)


class BudgetVersionORM(Base):
    """Snapshot inmutable de una version enviada (RF-P8-05). Solo INSERT:
    historial de reenvios."""

    __tablename__ = "budget_versions"
    id = Column(String, primary_key=True)
    budget_id = Column(String, ForeignKey("budgets.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    snapshot = Column(Text, nullable=False)  # JSON (customer, items, totals)
    created_at = Column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Fase 8 (P9/P10): PDF de presupuesto + auditoría WhatsApp
# ---------------------------------------------------------------------------


class BudgetDocumentORM(Base):
    """PDF generado de un presupuesto (P9). Clave (budget_id, content_hash):
    una fila vigente por presupuesto; editado el contenido → hash nuevo →
    la fila se reemplaza (no se conservan versiones del documento)."""

    __tablename__ = "budget_documents"
    id = Column(String, primary_key=True)
    budget_id = Column(
        String, ForeignKey("budgets.id"), nullable=False, unique=True, index=True
    )
    content_hash = Column(String, nullable=False)
    pdf_data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class BudgetEventORM(Base):
    """Evento de auditoría de presupuesto (whatsapp, ...). Solo INSERT:
    historial (misma política que order_events, Fase 6). El teléfono se
    guarda ENMASCARADO (RNF-P10-05)."""

    __tablename__ = "budget_events"
    id = Column(String, primary_key=True)
    budget_id = Column(String, ForeignKey("budgets.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)
