from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from backend.database.base import get_db
from backend.models.project import ProjectMember
from backend.models.user import User
from backend.schemas.Project import ProjectMemberResponse
from backend.middleware.auth import verify_token

router = APIRouter(prefix="/api/v1")

@router.get("/project_members", response_model=List[ProjectMemberResponse])
def list_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    memberships = (
        db.query(ProjectMember)
          .filter(ProjectMember.project_id == project_id)
          .all()
    )
    result = []
    for pm in memberships:
        user = db.query(User).filter(User.user_id == pm.user_id).first()
        if user:
            result.append(ProjectMemberResponse(user_id=user.user_id, name=user.name))
    return result
