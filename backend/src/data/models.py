from sqlalchemy import Column, String, DateTime, Integer, Boolean, Enum as SQLAlchemyEnum
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
    include_labor = Column(Boolean, default=True, nullable=False)
    include_gas = Column(Boolean, default=False, nullable=False)
    include_waste = Column(Boolean, default=False, nullable=False)
    default_prep_minutes = Column(Integer, default=30, nullable=False)
    default_servings = Column(Integer, default=6, nullable=False)
    default_difficulty = Column(String, default="simple", nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
