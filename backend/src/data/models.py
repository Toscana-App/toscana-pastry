
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class UserORM(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    google_id = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
