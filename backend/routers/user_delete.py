from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from sqlalchemy import case
from pydantic import BaseModel
from typing import Optional
from backend.models.user import User
from backend.models.user_setting import UserSetting
from backend.models.comment_file import Comment
from backend.models.logs_notification import Notification, ActivityLog
from backend.models.project import ProjectMember, Project
from backend.models.project_invitation import ProjectInvitation
from backend.models.workspace_project_order import WorkspaceProjectOrder
from backend.models.workspace import Workspace
from backend.models.task import Task, TaskMember
from backend.database.base import get_db
from backend.middleware.auth import verify_token
import bcrypt

router = APIRouter(prefix="/api/v1/user", tags=["UserDelete"])

class DeleteAccountRequest(BaseModel):
    confirmation_text: str
    password: Optional[str] = None  # 소셜 계정의 경우 비밀번호가 없을 수 있음

@router.delete("/delete", status_code=204)
def delete_account(
    request: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    user_id = current_user.user_id
    
    # 삭제 확인 문자열 검증
    if request.confirmation_text != "계정을 영구 삭제합니다":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="확인 문자를 정확히 입력해주세요."
        )
    
    # 소유하고 있는 프로젝트 처리
    owned_projects = db.query(Project).filter(Project.owner_id == user_id).all()
    
    for project in owned_projects:
        # 프로젝트의 다른 멤버들 찾기 (소유자 제외)
        other_members = db.query(ProjectMember).filter(
            ProjectMember.project_id == project.project_id,
            ProjectMember.user_id != user_id
        ).order_by(
            # 관리자 우선, 그 다음 멤버, 마지막에 뷰어
            case(
                (ProjectMember.role == "admin", 1),
                (ProjectMember.role == "member", 2), 
                (ProjectMember.role == "viewer", 3),
                else_=4
            )
        ).all()
        
        if other_members:
            # 다른 멤버가 있으면 첫 번째 멤버(가장 높은 권한)에게 소유권 이전
            new_owner = other_members[0]
            
            # 프로젝트 소유자 변경
            project.owner_id = new_owner.user_id
            
            # 새 소유자의 역할을 owner로 변경
            new_owner.role = "owner"
            
            print(f"프로젝트 '{project.title}' 소유권을 사용자 {new_owner.user_id}에게 이전")
        else:
            # 다른 멤버가 없으면 프로젝트와 관련 데이터 삭제
            print(f"프로젝트 '{project.title}' 삭제 (다른 멤버 없음)")
            
            # 프로젝트 관련 데이터 삭제
            db.query(ActivityLog).filter(ActivityLog.project_id == project.project_id).delete()
            db.query(ProjectMember).filter(ProjectMember.project_id == project.project_id).delete()
            db.query(ProjectInvitation).filter(ProjectInvitation.project_id == project.project_id).delete()
            db.query(WorkspaceProjectOrder).filter(WorkspaceProjectOrder.project_id == project.project_id).delete()
            
            # 프로젝트 삭제
            db.delete(project)
    
    # 변경사항 커밋
    db.commit()
    
    # 🔒 안전 확인: 소유권 이전이 제대로 되었는지 재확인
    remaining_owned_projects = db.query(Project).filter(Project.owner_id == user_id).all()
    if remaining_owned_projects:
        # 소유권이 제대로 이전되지 않은 프로젝트가 있다면 에러
        problem_projects = [p.title for p in remaining_owned_projects]
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"소유권 이전에 실패한 프로젝트가 있습니다: {', '.join(problem_projects)}. 관리자에게 문의하세요."
        )
    
    # 비밀번호 검증 (소셜 계정은 비밀번호 확인 건너뛰기)
    if current_user.provider == "local":  # 일반 계정인 경우에만 비밀번호 확인
        if not request.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="비밀번호를 입력해주세요."
            )
        if not bcrypt.checkpw(request.password.encode("utf-8"), current_user.password.encode("utf-8")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="비밀번호가 일치하지 않습니다."
            )
    # 소셜 계정의 경우 (provider != "local") 비밀번호 확인 건너뛰기

    # 1. 태스크 멤버 삭제
    db.query(TaskMember).filter(TaskMember.user_id == user_id).delete()
    # 2. 사용자가 담당자인 태스크의 assignee_id를 NULL로 설정
    db.query(Task).filter(Task.assignee_id == user_id).update({"assignee_id": None})
    # 3. 댓글의 user_id를 NULL로 설정 (댓글 내용은 유지)
    db.query(Comment).filter(Comment.user_id == user_id).update({"user_id": None})
    # 4. 알림 삭제
    db.query(Notification).filter(Notification.user_id == user_id).delete()
    
    # 5. 사용자의 활동 로그 삭제
    db.query(ActivityLog).filter(ActivityLog.user_id == user_id).delete()
    
    # 6. 사용자 본인의 프로젝트 멤버 관계 삭제
    db.query(ProjectMember).filter(ProjectMember.user_id == user_id).delete()
    
    # 7. 사용자가 초대한 초대 내역 삭제
    db.query(ProjectInvitation).filter(ProjectInvitation.invited_by == user_id).delete()
    # 13. 사용자 설정 삭제
    db.query(UserSetting).filter(UserSetting.user_id == user_id).delete()
    # 14. 워크스페이스 삭제 (본인이 소유한 워크스페이스)
    db.query(Workspace).filter(Workspace.user_id == user_id).delete()
    # 15. 사용자 계정 삭제
    db.delete(current_user)
    db.commit()
    return 