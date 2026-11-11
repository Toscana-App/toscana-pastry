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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC))


class RefreshTokenORM(Base):

    __tablename__ = "refresh_tokens"
    jti = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    family_id = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC))

class BusinessSettingsORM(Base):
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
    business_name = Column(String, default="", nullable=False)
    footer_text = Column(String, default="", nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC))


class IngredientORM(Base):

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

    __tablename__ = "products"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    prep_time_min = Column(Integer, nullable=False, default=0)
    servings = Column(Integer, nullable=False, default=1)
    difficulty = Column(String, nullable=False, default="simple")
    available = Column(Boolean, nullable=False, default=False, index=True)
    image_url = Column(String, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    recipe_items = relationship(
        "RecipeItemORM",
        cascade="all, delete-orphan",
        order_by="RecipeItemORM.position",
        lazy="selectin",
    )


class RecipeItemORM(Base):

    __tablename__ = "recipe_items"
    id = Column(String, primary_key=True)
    product_id = Column(
        String, ForeignKey("products.id"), nullable=False, index=True
    )
    ingredient_id = Column(String, nullable=False, index=True)
    qty = Column(Text, nullable=False)
    unit = Column(String, nullable=False)
    position = Column(Integer, nullable=False, default=0)


class CustomerORM(Base):

    __tablename__ = "customers"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=False)
    name_norm = Column(String, nullable=False, index=True)
    phone_norm = Column(String, nullable=False)
    delivery_address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        {"extend_existing": True},
    )


class OrderEventORM(Base):

    __tablename__ = "order_events"
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)


class TenantSequenceORM(Base):

    __tablename__ = "tenant_sequences"
    key = Column(String, primary_key=True)
    current = Column(Integer, nullable=False, default=0)


class BudgetORM(Base):

    __tablename__ = "budgets"
    id = Column(String, primary_key=True)
    seq = Column(String, nullable=False, unique=True, index=True)
    customer_id = Column(
        String, ForeignKey("customers.id"), nullable=False, index=True
    )
    customer_name = Column(String, nullable=False, index=True)
    customer_phone = Column(String, nullable=False)
    delivery_address = Column(String, nullable=True)
    status = Column(String, nullable=False, default="borrador", index=True)
    calculation_mode = Column(String, nullable=False, default="cost_plus")
    margin_pct = Column(String, nullable=True)
    version = Column(Integer, nullable=False, default=0)
    sent_at = Column(DateTime(timezone=True), nullable=True)
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

    __tablename__ = "budget_items"
    id = Column(String, primary_key=True)
    budget_id = Column(String, ForeignKey("budgets.id"), nullable=False, index=True)
    product_id = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=False)
    qty = Column(Integer, nullable=False)
    unit_cost = Column(String, nullable=False)
    unit_selling = Column(String, nullable=False)
    price_overridden = Column(Boolean, nullable=False, default=False)
    position = Column(Integer, nullable=False, default=0)


class BudgetVersionORM(Base):

    __tablename__ = "budget_versions"
    id = Column(String, primary_key=True)
    budget_id = Column(String, ForeignKey("budgets.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    snapshot = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class BudgetDocumentORM(Base):

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

    __tablename__ = "budget_events"
    id = Column(String, primary_key=True)
    budget_id = Column(String, ForeignKey("budgets.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    payload = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)

class CalcSettingsORM(Base):

    __tablename__ = "calc_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    business_name = Column(String, nullable=False, default="Mi Negocio")
    main_currency_name = Column(String, nullable=False, default="Peso")
    main_currency_symbol = Column(String, nullable=False, default="$")
    default_margin_percent = Column(String, nullable=False, default="30")
    default_discount_percent = Column(String, nullable=False, default="0")
    default_tax_percent = Column(String, nullable=False, default="19")
    rounding_mode = Column(String, nullable=False, default="none")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC))


class CalcMaterialCategoryORM(Base):

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

    __tablename__ = "customer_addresses"
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

    __tablename__ = "calc_material_cost_history"
    id = Column(String, primary_key=True)
    material_id = Column(
        String, ForeignKey("calc_materials.id"), nullable=False, index=True
    )
    previous_unit_cost = Column(String, nullable=True)
    new_unit_cost = Column(String, nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=False)


class CalcProductORM(Base):

    __tablename__ = "calc_products"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    sku = Column(String, nullable=True, index=True)
    product_category_id = Column(
        String, ForeignKey("calc_product_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
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

    __tablename__ = "calc_product_materials"
    id = Column(String, primary_key=True)
    product_id = Column(
        String, ForeignKey("calc_products.id"), nullable=False, index=True
    )
    material_id = Column(
        String, ForeignKey("calc_materials.id"), nullable=True, index=True
    )
    material_name = Column(String, nullable=False)
    unit_of_measure_snapshot = Column(String, nullable=True)
    unit_cost_snapshot = Column(String, nullable=False)
    quantity_used = Column(String, nullable=False)
    line_total_cost = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False)


class CalcProductLaborORM(Base):

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


class CartORM(Base):

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


class _OrderStatusColumn(TypeDecorator):

    impl = String(20)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None:
            return str(value).lower()
        return value


class _PaymentMethodColumn(TypeDecorator):

    impl = String(20)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None:
            return str(value).lower()
        return value


class _PaymentStatusColumn(TypeDecorator):

    impl = String(20)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None:
            return str(value).lower()
        return value


class OrderORM(Base):

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
    paid_at = Column(DateTime(timezone=True), nullable=True)
    payment_status = Column(_PaymentStatusColumn(), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    customer_name = Column(String, nullable=True, index=True)
    customer_phone = Column(String, nullable=True)
    margin_pct = Column(String, nullable=True)
    whatsapp_sent_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    order_items = relationship("OrderItemORM", back_populates="order", cascade="all, delete-orphan")


class OrderWindowORM(Base):

    __tablename__ = "order_window"

    id = Column(String, primary_key=True, default="singleton")
    open = Column(Boolean, default=True, nullable=False)
    reopens_at = Column(DateTime(timezone=True), nullable=True)
    message = Column(String, default="", nullable=False)


class OrderItemORM(Base):

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
    portions = Column(Integer, nullable=True)
    note = Column(Text, nullable=False, default="")
    position = Column(Integer, nullable=False, default=0)
    snapshot = Column(Text, nullable=True)


class PaymentAttemptORM(Base):

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


class ImportSessionORM(Base):

    __tablename__ = "import_sessions"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    entity = Column(String, nullable=False)
    status = Column(String, nullable=False, default="received", index=True)
    filename = Column(String, nullable=False)
    delimiter = Column(String, nullable=False)
    encoding = Column(String, nullable=False)
    template_columns = Column(Text, nullable=False)
    total_rows = Column(Integer, nullable=False, default=0)
    valid_rows = Column(Integer, nullable=False, default=0)
    invalid_rows = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    confirmed_at = Column(DateTime(timezone=True), nullable=True)


class ImportRowORM(Base):

    __tablename__ = "import_rows"

    id = Column(String, primary_key=True)
    import_id = Column(
        String, ForeignKey("import_sessions.id"), nullable=False, index=True
    )
    tenant_id = Column(String, nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="valid")
    data = Column(Text, nullable=False)
    errors = Column(Text, nullable=False, default="[]")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
