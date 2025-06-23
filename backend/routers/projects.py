from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database.base import get_db
from backend.models.project import Project, ProjectMember
from backend.models.user import User
from backend.middleware.auth import verify_token
from backend.routers.notifications import create_notification, create_project_notification

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
    db.flush()

    # 새 멤버에게 알림 생성 (적절한 함수 사용)
    await create_project_notification(
        db=db,
        user_id=user_id,
        project_id=project_id,
        project_name=project.title,
        notification_type="project_member_added",
        actor_name=current_user.name
    )
    
    # WebSocket 이벤트 발행 - 프로젝트 멤버 추가
    try:
        from backend.websocket.events import event_emitter
        # 사용자 정보 조회
        added_user = db.query(User).filter(User.user_id == user_id).first()
        
        await event_emitter.emit_project_member_added(
            project_id=project_id,
            workspace_id=0,  # 직접 추가이므로 workspace_id가 명확하지 않음, 필요시 파라미터로 받을 수 있음
            project_name=project.title,
            member_id=user_id,
            member_name=added_user.name if added_user else "Unknown User",
            role=role,
            added_by=current_user.user_id
        )
    except Exception as e:
        print(f"WebSocket 프로젝트 멤버 추가 이벤트 발행 실패: {str(e)}")
    
    db.commit()
    return member 
