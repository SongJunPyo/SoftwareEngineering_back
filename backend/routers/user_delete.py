from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from backend.models.user import User
from backend.models.user_setting import UserSetting
from backend.models.comment_file import Comment
from backend.models.logs_notification import Notification, ActivityLog
from backend.models.project import ProjectMember, Project
from backend.models.workspace import Workspace
from backend.database.base import get_db
from backend.middleware.auth import verify_token
import bcrypt

router = APIRouter(prefix="/api/v1/user", tags=["UserDelete"])

@router.delete("/delete", status_code=204)
def delete_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    user_id = current_user.user_id

    # 1. 댓글 삭제
    db.query(Comment).filter(Comment.user_id == user_id).delete()
    # 2. 알림 삭제
    db.query(Notification).filter(Notification.user_id == user_id).delete()
    # 3. 활동 로그 삭제
    db.query(ActivityLog).filter(ActivityLog.user_id == user_id).delete()
    # 4. 프로젝트 멤버 삭제
    db.query(ProjectMember).filter(ProjectMember.user_id == user_id).delete()
    # 5. 사용자 설정 삭제
    db.query(UserSetting).filter(UserSetting.user_id == user_id).delete()
    # 6. 워크스페이스 삭제 (본인이 소유한 워크스페이스)
    db.query(Workspace).filter(Workspace.user_id == user_id).delete()
    # 7. 사용자 계정 삭제
    db.delete(current_user)
    db.commit()
    return 