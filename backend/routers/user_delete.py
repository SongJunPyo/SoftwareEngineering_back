from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
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
    password: str

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
    
    # 비밀번호 검증
    if not current_user.password or not bcrypt.checkpw(request.password.encode("utf-8"), current_user.password.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 일치하지 않습니다."
        )

    # 1. 태스크 멤버 삭제
    db.query(TaskMember).filter(TaskMember.user_id == user_id).delete()
    # 2. 사용자가 담당자인 태스크의 assignee_id를 NULL로 설정
    db.query(Task).filter(Task.assignee_id == user_id).update({"assignee_id": None})
    # 3. 댓글의 user_id를 NULL로 설정 (댓글 내용은 유지)
    db.query(Comment).filter(Comment.user_id == user_id).update({"user_id": None})
    # 4. 알림 삭제
    db.query(Notification).filter(Notification.user_id == user_id).delete()
    # 5. 사용자가 소유한 프로젝트의 활동 로그 삭제 (먼저 수행)
    user_projects_for_logs = db.query(Project.project_id).filter(Project.owner_id == user_id)
    user_project_ids_for_logs = [p.project_id for p in user_projects_for_logs.all()]
    
    if user_project_ids_for_logs:
        db.query(ActivityLog).filter(ActivityLog.project_id.in_(user_project_ids_for_logs)).delete(synchronize_session=False)
    
    # 6. 사용자의 활동 로그 삭제
    db.query(ActivityLog).filter(ActivityLog.user_id == user_id).delete()
    
    # 7. 사용자가 소유한 프로젝트의 모든 멤버 삭제 (다른 사용자들도 포함)
    if user_project_ids_for_logs:
        db.query(ProjectMember).filter(ProjectMember.project_id.in_(user_project_ids_for_logs)).delete(synchronize_session=False)
    
    # 8. 사용자 본인의 프로젝트 멤버 관계 삭제 (혹시 남은 것들)
    db.query(ProjectMember).filter(ProjectMember.user_id == user_id).delete()
    
    # 9. 사용자가 소유한 프로젝트의 초대 내역 삭제
    if user_project_ids_for_logs:
        db.query(ProjectInvitation).filter(ProjectInvitation.project_id.in_(user_project_ids_for_logs)).delete(synchronize_session=False)
    
    # 10. 사용자가 초대한 초대 내역 삭제
    db.query(ProjectInvitation).filter(ProjectInvitation.invited_by == user_id).delete()
    
    # 11. 사용자가 소유한 프로젝트의 워크스페이스 순서 삭제
    if user_project_ids_for_logs:
        db.query(WorkspaceProjectOrder).filter(WorkspaceProjectOrder.project_id.in_(user_project_ids_for_logs)).delete(synchronize_session=False)
    
    # 12. 사용자가 소유한 프로젝트 삭제 (CASCADE로 관련 데이터 자동 삭제)
    db.query(Project).filter(Project.owner_id == user_id).delete()
    # 13. 사용자 설정 삭제
    db.query(UserSetting).filter(UserSetting.user_id == user_id).delete()
    # 14. 워크스페이스 삭제 (본인이 소유한 워크스페이스)
    db.query(Workspace).filter(Workspace.user_id == user_id).delete()
    # 15. 사용자 계정 삭제
    db.delete(current_user)
    db.commit()
    return 