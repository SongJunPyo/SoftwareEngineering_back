from sqlalchemy import Column, Integer, Text, ForeignKey
from backend.database.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    workspace_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    order = Column(Integer, nullable=True)