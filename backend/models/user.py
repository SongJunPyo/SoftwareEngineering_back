from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from backend.database.base import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False, default="local")
    role = Column(String, nullable=False, default="member")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    email_notifications_enabled = Column(Boolean, nullable=False, default=True)
    notification_email = Column(String, nullable=True)
    
    # 이메일 인증 관련 필드들
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verification_token = Column(String, nullable=True)
    email_verification_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    tasks = relationship("Task", back_populates="assignee")