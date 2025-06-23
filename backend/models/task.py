from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Date, Boolean
from sqlalchemy.orm import relationship
from backend.database.base import Base


class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    parent_task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="SET NULL"))
    title = Column(Text, nullable=False)
    description = Column(Text)
    assignee_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    priority = Column(Text, nullable=False, default="medium")
    start_date = Column(Date, nullable=False, default=lambda: date.today())
    due_date = Column(Date, nullable=False, default=lambda: date.today())
    status = Column(Text, nullable=False, default="todo")
    is_parent_task = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    assignee = relationship("User", back_populates="tasks")
    parent_task = relationship("Task", remote_side=[task_id], backref="subtasks")

class TaskMember(Base):
    __tablename__ = "task_members"

    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
