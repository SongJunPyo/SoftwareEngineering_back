from sqlalchemy import Column, Integer, Text, ForeignKey
from backend.database.base import Base


class Tag(Base):
    __tablename__ = "tags"

    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True)
    tag_name = Column(Text, nullable=False, primary_key=True)


class TaskTag(Base):
    __tablename__ = "task_tags"

    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), primary_key=True)
    tag_name = Column(Text, nullable=False, primary_key=True)
