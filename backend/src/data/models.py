from sqlalchemy import Column, String, DateTime, Integer, Boolean, Enum as SQLAlchemyEnum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, declarative_base
from sqlalchemy import TypeDecorator
import datetime
import enum

Base = declarative_base()

class UserRoleEnum(str, enum.Enum):
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
