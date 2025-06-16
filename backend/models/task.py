from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.base import Base


class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    parent_task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="SET NULL"))
    title = Column(Text, nullable=False)
    description = Column(Text)
    assignee_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"),nullable=False)
    priority = Column(Text, nullable=False, default="medium")
    start_date = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    due_date = Column(DateTime,  nullable=False, default=lambda: datetime.now(timezone.utc))
    status = Column(Text, nullable=False, default="todo")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    assignee = relationship("User", back_populates="tasks")

class TaskMember(Base):
    __tablename__ = "task_members"

    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
