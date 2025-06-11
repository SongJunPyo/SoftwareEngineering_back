from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, BigInteger, ForeignKey
from backend.database.base import Base

class Comment(Base):
    __tablename__ = "comments"

    comment_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    is_updated = Column(Integer, nullable=False, default=0)  # 0: not updated(작성됨), 1: updated(수정됨)

class File(Base):
    __tablename__ = "files"

    file_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"))
    comment_id = Column(Integer, ForeignKey("comments.comment_id", ondelete="CASCADE"))
    file_name = Column(Text, nullable=False)
    file_url = Column(Text, nullable=False)
    mime_type = Column(Text)
    file_size = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
