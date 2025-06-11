<<<<<<< HEAD
from sqlalchemy import Column, Integer, Text, ForeignKey
from backend.database.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    workspace_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    order = Column(Integer, nullable=True)
=======
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from backend.database.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    workspace_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
>>>>>>> 87e167ddb096e85420193818f982a517a789eea7
