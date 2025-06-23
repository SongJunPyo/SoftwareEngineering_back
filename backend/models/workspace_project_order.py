from sqlalchemy import Column, Integer, ForeignKey
from backend.database.base import Base

class WorkspaceProjectOrder(Base):
    __tablename__ = "workspace_project_order"

    workspace_id = Column(Integer, ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True)
    project_order = Column(Integer, nullable=False)