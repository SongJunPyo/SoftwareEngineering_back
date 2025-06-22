from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database.base import get_db
from backend.models.project import Project, ProjectMember
from backend.models.user import User
from backend.middleware.auth import verify_token
from backend.routers.notifications import create_notification

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

@router.post("/{project_id}/members")
async def add_project_member(
    project_id: int,
    user_id: int,
    role: str = "member",
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # 프로젝트 소유자 확인
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project or project.owner_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # 새 멤버 추가
    member = ProjectMember(
        project_id=project_id,
        user_id=user_id,
        role=role
    )
    db.add(member)
    db.commit()

    # 새 멤버에게 알림 생성
    await create_notification(
        db=db,
        user_id=user_id,
        type="project",
        message=f"'{project.title}' 프로젝트에 초대되었습니다.",
        channel="project"
    )

    return member 
