from datetime import datetime, timezone
from sqlalchemy import Column, Integer,String,Enum, Text, DateTime, Boolean, ForeignKey
from backend.database.base import Base
from sqlalchemy.orm import relationship
class Project(Base):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    status = Column(Text, nullable=False, default="active")
    owner_id = Column(Integer, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    order = Column(Integer, nullable=False, default=0)
    members = relationship(
        "ProjectMember",
        backref="project",
        cascade="all, delete-orphan",
        lazy="joined"  # 또는 lazy="selectin" 도 OK
    )
class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id = Column(Integer, ForeignKey("projects.project_id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    role = Column(Text, nullable=False, default="contributor")
    view_permission = Column(Boolean, nullable=False, default=True)
    email = Column(String(255), nullable=False)
    
    user = relationship("User", backref="project_memberships", lazy="joined")
class ProjectInvitation(Base):
    __tablename__ = "project_invitations"
    
    project_inv_id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"))
    email = Column(String(255), nullable=False)
    invited_by = Column(Integer, ForeignKey("users.user_id"))
    status = Column(Enum("pending", "accepted", "expired", name="invitation_status"), default="pending")
