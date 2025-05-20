from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from backend.database.base import Base


class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    parent_task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="SET NULL"))
    title = Column(Text, nullable=False)
    description = Column(Text)
    assignee_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    priority = Column(Text, nullable=False, default="medium")
    due_date = Column(DateTime)
    status = Column(Text, nullable=False, default="todo")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
