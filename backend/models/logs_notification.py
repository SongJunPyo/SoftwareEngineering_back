from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, Boolean, ForeignKey, String, Table
from backend.database.base import Base
import asyncio
from pydantic import BaseModel
from typing import Optional

class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    type = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    channel = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    related_id = Column(Integer, nullable=True)  # 관련 엔티티의 ID (task_id, project_id 등)
    
    def to_dict(self):
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "type": self.type,
            "message": self.message,
            "channel": self.channel,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "related_id": self.related_id
        }


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    user_name = Column(String, nullable=True)  # 작성자 이름
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(Text, nullable=False)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="SET NULL"), nullable=True)
    project_name = Column(String, nullable=True)  # 프로젝트명
    details = Column(Text, nullable=True)         # 상세 내용(댓글/업무제목)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class LogResponse(BaseModel):
    log_id: int
    user_id: int
    user_name: Optional[str]
    entity_type: str
    entity_id: int
    action: str
    project_id: Optional[int]
    project_name: Optional[str]
    details: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


# 이 클래스는 SQLAlchemy 메타데이터 바인딩 문제로 오류를 유발하므로 제거합니다.
# class LogResponseView(Base):
#     __tablename__ = "log_responses"
#     __table_args__ = {'autoload_with': Base.metadata.bind}

#     log_id = Column(Integer, primary_key=True)
#     user_id = Column(Integer)
#     user_name = Column(String)
#     entity_type = Column(Text)
#     entity_id = Column(Integer)
#     action = Column(Text)
#     project_id = Column(Integer)
#     project_name = Column(String)
#     details = Column(Text)
#     timestamp = Column(DateTime)

