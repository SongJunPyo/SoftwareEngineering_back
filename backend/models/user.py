from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from database.base import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    phone_number = Column(String(20), nullable=False)
    address = Column(String(150), nullable=False)
    account_type = Column(Integer, nullable=False, default=3)
    approved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))