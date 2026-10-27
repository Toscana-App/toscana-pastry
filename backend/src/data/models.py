from sqlalchemy import Column, String, DateTime, Integer, Boolean, Enum as SQLAlchemyEnum, ForeignKey
from sqlalchemy.orm import declarative_base
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
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
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
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
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
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
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
