from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from database.base import Base

class User(Base):
    __tablename__ = "user"  # 테이블 이름

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    name = Column(String(50), nullable=False)
    phone_number = Column(String(20), nullable=False)
    address = Column(String(150), nullable=False)

    # 관리자 1, 병원 2, 사용자 3, 나중에 동물도 필요할듯
    account_type = Column(Integer, nullable=False, default=3)
    # 승인 여부
    approved = Column(Boolean, default=False)

    created_time = Column(DateTime, default=datetime.utcnow)