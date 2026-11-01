import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


class UserRoleEnum(StrEnum):
    ADMIN = "admin"
    CUSTOMER = "customer"
    NEGOCIO = "negocio"


class _UserRoleColumn(TypeDecorator):
    """Stores the user role as a lowercase string.

    Replaces SQLAlchemyEnum to avoid the footgun where legacy uppercase
    values (e.g. "ADMIN" from old backups or hand-edited rows) raise
    LookupError during ORM loading.  The column stores plain TEXT in the
    database and normalises every value to lowercase on read, so
    _to_domain can safely do ``UserRole(raw_value)``.
    """

    impl = String(50)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None:
            return str(value).lower()
        return value


class UserORM(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    google_id = Column(String, unique=True, nullable=True)
    role = Column(
        _UserRoleColumn(),
        default="customer",
        nullable=False,
    )
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
    consumer_markup_pct = Column(String, default="40", nullable=False)
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
        default=lambda: datetime.datetime.now(datetime.UTC),
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
    seq = Column(String, nullable=False, unique=True, index=True)
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
    # Pedido creado al convertir; nulo = aun no convertido (RF-P8-08).
    order_id = Column(
        String, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
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

class CalcSettingsORM(Base):
    """Configuracion de la calculadora de costos (singleton, RF-P5CC-01/02).

    Montos como TEXT (no float): SQLite no tiene decimal y float pierde precision.
    """

    __tablename__ = "calc_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    business_name = Column(String, nullable=False, default="Mi Negocio")
    main_currency_name = Column(String, nullable=False, default="Peso")
    main_currency_symbol = Column(String, nullable=False, default="$")
    default_margin_percent = Column(String, nullable=False, default="30")
    default_discount_percent = Column(String, nullable=False, default="0")
    default_tax_percent = Column(String, nullable=False, default="19")
    rounding_mode = Column(String, nullable=False, default="none")
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class CalcMaterialCategoryORM(Base):
    """Categoria de materiales (RF-P5CC-03)."""

    __tablename__ = "calc_material_categories"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class CalcProductCategoryORM(Base):
    """Categoria de productos (RF-P5CC-04)."""

    __tablename__ = "calc_product_categories"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class CalcSupplierORM(Base):
    """Proveedor (RF-P5CC-05)."""

    __tablename__ = "calc_suppliers"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    contact_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class CustomerAddressORM(Base):
    """Direccion de entrega de un cliente (RF-P11-09). Exactamente una
    is_default=True por user_id (invariant a nivel de dominio)."""

    __tablename__ = "customer_addresses"
    # At most one default per user, enforced by the DB (partial unique index).
    __table_args__ = (
        Index(
            "uq_customer_addresses_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default"),
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    street_line_1: Mapped[str] = mapped_column(String, nullable=False)
    street_line_2: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    province: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class CouponORM(Base):
    """Cupon de descuento (RF-P11-14, C3).

    Unicidad case/accent-insensitive de `code` via `code_key`: columna
    persistida con accent_fold(code) (la calcula el repositorio) y
    UNIQUE a nivel DB (migracion 0002). `value` se guarda como str
    (Money). C4 consumira `uses`/`max_uses` al confirmar pedidos.
    """

    __tablename__ = "coupons"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, nullable=False, index=True)
    code_key: Mapped[str] = mapped_column(
        String, nullable=False, unique=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    valid_from: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class CalcMaterialORM(Base):
    """Material de la calculadora de costos (RF-P2CC-01).

    Montos/cantidades como TEXT (no float): SQLite no tiene tipo decimal
    y convertir por float pierde precision, que en dinero no se tolera
    (RNF-P5CC-01). `unit_cost`/`status` son derivados del servidor
    (RF-P2CC-02/03). None en precio o cantidad = "sin dato" -> `incomplete`.
    """

    __tablename__ = "calc_materials"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    internal_code = Column(String, nullable=True)
    unit_of_measure = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    material_category_id = Column(
        String, ForeignKey("calc_material_categories.id"), nullable=True, index=True
    )
    supplier_id = Column(
        String, ForeignKey("calc_suppliers.id"), nullable=True, index=True
    )
    purchase_total_price = Column(String, nullable=True)
    package_quantity = Column(String, nullable=True)
    unit_cost = Column(String, nullable=True)
    status = Column(String, nullable=False, default="incomplete")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class CalcMaterialCostHistoryORM(Base):
    """Historial append-only de costo unitario por material (RF-P2CC-04).

    Solo INSERT, nunca UPDATE/DELETE (estilo StockMovementORM, RF-P2-04).
    """

    __tablename__ = "calc_material_cost_history"
    id = Column(String, primary_key=True)
    material_id = Column(
        String, ForeignKey("calc_materials.id"), nullable=False, index=True
    )
    previous_unit_cost = Column(String, nullable=True)
    new_unit_cost = Column(String, nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=False)


class CalcProductORM(Base):
    """Producto de la calculadora de costos (RF-P4CC-01).

    Montos como TEXT (no float): SQLite no tiene tipo decimal y
    convertir por float pierde precision, que en dinero no se tolera
    (RNF-P5CC-01). `deleted_at` no nulo = soft delete (regla 8).
    """

    __tablename__ = "calc_products"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    sku = Column(String, nullable=True, index=True)
    product_category_id = Column(
        String, ForeignKey("calc_product_categories.id"), nullable=True, index=True
    )
    description = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    margin_percent = Column(String, nullable=False)
    discount_percent = Column(String, nullable=False)
    tax_percent = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    last_recalculated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class CalcProductMaterialORM(Base):
    """Linea de material con snapshots resueltos por el servidor
    (RF-P4CC-02, security #8). Montos/cantidades como TEXT."""

    __tablename__ = "calc_product_materials"
    id = Column(String, primary_key=True)
    product_id = Column(
        String, ForeignKey("calc_products.id"), nullable=False, index=True
    )
    material_id = Column(
        String, ForeignKey("calc_materials.id"), nullable=False, index=True
    )
    material_name = Column(String, nullable=False)
    unit_of_measure_snapshot = Column(String, nullable=True)
    unit_cost_snapshot = Column(String, nullable=False)
    quantity_used = Column(String, nullable=False)
    line_total_cost = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False)


class CalcProductLaborORM(Base):
    """Linea de mano de obra (RF-P4CC-02). Montos como TEXT."""

    __tablename__ = "calc_product_labor"
    id = Column(String, primary_key=True)
    product_id = Column(
        String, ForeignKey("calc_products.id"), nullable=False, index=True
    )
    activity_name = Column(String, nullable=False)
    hourly_rate = Column(String, nullable=False)
    minutes_required = Column(String, nullable=False)
    line_total_cost = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False)


class CalcProductExtraCostORM(Base):
    """Linea de costo extra (RF-P4CC-02). Montos/cantidades como TEXT."""

    __tablename__ = "calc_product_extra_costs"
    id = Column(String, primary_key=True)
    product_id = Column(
        String, ForeignKey("calc_products.id"), nullable=False, index=True
    )
    concept_name = Column(String, nullable=False)
    unit_cost = Column(String, nullable=False)
    quantity = Column(String, nullable=False)
    line_total_cost = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False)


class CalcProductVersionORM(Base):
    """Version append-only del precio del producto (RF-P4CC-07).

    Solo INSERT, nunca UPDATE/DELETE. Montos como TEXT (centavos).
    """

    __tablename__ = "calc_product_versions"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "version_number",
            name="uq_calc_product_versions_product_version",
        ),
    )
    id = Column(String, primary_key=True)
    product_id = Column(
        String, ForeignKey("calc_products.id"), nullable=False, index=True
    )
    version_number = Column(Integer, nullable=False)
    product_total_cost = Column(String, nullable=False)
    profit_amount = Column(String, nullable=False)
    discount_amount = Column(String, nullable=False)
    adjusted_profit_amount = Column(String, nullable=False)
    tax_amount = Column(String, nullable=False)
    final_sale_price = Column(String, nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False)


class CalcDefaultCostORM(Base):
    """Costo por defecto (RF-P5CC-06)."""

    __tablename__ = "calc_default_costs"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    default_unit_cost_or_rate = Column(String, nullable=False)
    default_quantity_or_minutes = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


# ─── Cart models (RF-P11-03/14, C4) ─────────────────────────────────


class CartORM(Base):
    """Carrito server-side por usuario (RF-P11-03). Un registro por user;
    `coupon_code` es el cupon aplicado (max 1 por carrito). El precio NO
    se persiste: solo product_id + qty (RNF-P11-03)."""

    __tablename__ = "cart"
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), primary_key=True
    )
    coupon_code: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class CartItemORM(Base):
    """Linea del carrito: (user_id, product_id) unico."""

    __tablename__ = "cart_items"
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), primary_key=True
    )
    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


# ─── Order models (RF-P6-12, C1) ─────────────────────────────────────


class _OrderStatusColumn(TypeDecorator):
    """Stores order status as a lowercase string."""

    impl = String(20)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None:
            return str(value).lower()
        return value


class _PaymentMethodColumn(TypeDecorator):
    """Stores payment_method as a lowercase string."""

    impl = String(20)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None:
            return str(value).lower()
        return value


class _PaymentStatusColumn(TypeDecorator):
    """Stores payment_status as a lowercase string."""

    impl = String(20)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None:
            return str(value).lower()
        return value


class OrderORM(Base):
    """Order entity with payment tracking and portal fields (RF-P6-12 / RF-P11-06/08)."""

    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    customer_id = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False, unique=True, index=True)
    status = Column(_OrderStatusColumn(), default="nuevo", nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    payment_method = Column(_PaymentMethodColumn(), default="cash", nullable=False)
    delivery_mode = Column(String, default="delivery", nullable=False)
    delivery_address = Column(String, default="", nullable=False)
    coupon_code = Column(String, nullable=True)
    discount_amount = Column(String, nullable=True)
    payment_reference = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    payment_status = Column(_PaymentStatusColumn(), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    # P6 (admin): snapshot del cliente + margen override + auditoria WhatsApp.
    customer_name = Column(String, nullable=True, index=True)
    customer_phone = Column(String, nullable=True)
    margin_pct = Column(String, nullable=True)  # override; nulo = tenant
    whatsapp_sent_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    order_items = relationship("OrderItemORM", back_populates="order", cascade="all, delete-orphan")


class OrderWindowORM(Base):
    """Singleton configuration for the portal order window (RF-P5-07)."""

    __tablename__ = "order_window"

    id = Column(String, primary_key=True, default="singleton")
    open = Column(Boolean, default=True, nullable=False)
    reopens_at = Column(DateTime, nullable=True)
    message = Column(String, default="", nullable=False)


class OrderItemORM(Base):
    """Order line item snapshot."""

    __tablename__ = "order_items"

    id = Column(String, primary_key=True)
    order = relationship("OrderORM", back_populates="order_items")
    order_id = Column(
        String, ForeignKey("orders.id"), nullable=False, index=True
    )
    product_id = Column(String, nullable=False)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(String, nullable=True)
    portion_note = Column(String, default="", nullable=False)
    # P6 (admin): snapshot congelado del desglose (JSON, RNF-P6-03).
    qty = Column(Integer, nullable=True)
    portions = Column(Integer, nullable=True)
    note = Column(Text, nullable=False, default="")
    position = Column(Integer, nullable=False, default=0)
    snapshot = Column(Text, nullable=True)


class PaymentAttemptORM(Base):
    """Saved response of POST /orders/{id}/payment per Idempotency-Key (C1.4).

    ``id`` is ``"{order_id}:{idempotency_key}"``; a replay with the same key
    returns the stored reference/checkout_url instead of a new preference.
    """

    __tablename__ = "payment_attempts"

    id = Column(String, primary_key=True)
    order_id = Column(
        String, ForeignKey("orders.id"), nullable=False, index=True
    )
    reference = Column(String, nullable=False)
    checkout_url = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class PaymentEventORM(Base):
    """Webhook payment event for dedupe (RF-P6-13, RNF-P6-10).

    ``id`` is ``"{provider_payment_id}:{status}"``: Mercado Pago notifies one
    payment several times as its status changes (pending → approved), so
    each (payment, status) pair is recorded exactly once. Replays hit the
    primary key and return 200 without side effects.
    """

    __tablename__ = "payment_events"

    id = Column(String, primary_key=True)
    provider_payment_id = Column(String, nullable=False, index=True)
    order_id = Column(
        String, ForeignKey("orders.id"), nullable=False, index=True
    )
    status = Column(_PaymentStatusColumn(), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class LeadORM(Base):
    """Lead de contacto publico (RF-P11-13, C5).

    Captura formularios de contacto del portal — nombre, email, tipo de
    cliente, mensaje y campos opcionales.  `read` controla si el admin
    ya lo reviso.
    """

    __tablename__ = "leads"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    customer_type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    location = Column(String, nullable=True)
    read = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class WhatsAppSendORM(Base):
    """Registro de envio de WhatsApp (RF-P10-07/08, C7).

    `status` avanza por prioridad sent -> delivered -> read; `failed`
    es terminal (el reintento lo resetea a sent con nuevo `message_id`).
    `provider=wa_me` no tiene estados de entrega ni `message_id`.
    """

    __tablename__ = "whatsapp_sends"

    id = Column(String, primary_key=True)
    provider = Column(String, nullable=False)
    phone = Column(String, nullable=False, index=True)
    message = Column(String, nullable=False)
    reference_kind = Column(String, nullable=False)
    reference_id = Column(String, nullable=False, index=True)
    status = Column(String, default="sent", nullable=False, index=True)
    message_id = Column(String, nullable=True, index=True)
    failed_reason = Column(String, nullable=True)
    sent_at = Column(
        DateTime(timezone=True), nullable=False, index=True
    )
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
