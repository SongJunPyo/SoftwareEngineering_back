from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from backend.database.base import Base

class ProjectInvitation(Base):
    __tablename__ = "project_invitations"

    project_inv_id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    email = Column(String(255), nullable=False)
    invited_by = Column(Integer, ForeignKey("users.user_id"))
    status = Column(Enum("pending", "accepted", "expired", name="invitation_status"), default="pending")
    accepted_at = Column(DateTime, nullable=True)  # 수락 시간 필드

