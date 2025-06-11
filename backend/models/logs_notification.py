<<<<<<< HEAD
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, Boolean, ForeignKey
from backend.database.base import Base

class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    type = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    channel = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "type": self.type,
            "message": self.message,
            "channel": self.channel,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(Text, nullable=False)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="SET NULL"), nullable=True)
=======
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, Boolean, ForeignKey
from backend.database.base import Base

class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    type = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    channel = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(Text, nullable=False)
>>>>>>> 87e167ddb096e85420193818f982a517a789eea7
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))