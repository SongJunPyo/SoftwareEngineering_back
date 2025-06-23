from sqlalchemy import Column, Integer, Text, ForeignKey
from backend.database.base import Base

class UserSetting(Base):
    __tablename__ = "user_setting"

    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    email = Column(Text, nullable=False)
    nickname = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    img_path = Column(Text, nullable=True)