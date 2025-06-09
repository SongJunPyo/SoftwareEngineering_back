from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime
from backend.database.base import Base

class ProjectInvitation(Base):
    __tablename__ = "project_invitations"

    project_inv_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    email = Column(String(255), nullable=False)
    invited_by = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    role = Column(Enum("viewer", "member", "admin", "owner", name="invitation_role"), default="member", nullable=False)
    status = Column(Enum("pending", "accepted", "rejected", name="invitation_status"), default="pending")
    invited_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    accepted_at = Column(DateTime(timezone=True), nullable=True)