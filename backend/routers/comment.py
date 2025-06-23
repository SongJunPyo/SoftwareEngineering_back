from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.base import get_db
from backend.models.comment_file import Comment
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
from backend.middleware.auth import verify_token
from backend.models.task import Task
from backend.routers.notifications import create_notification, create_comment_notification
from backend.models.logs_notification import ActivityLog
from backend.websocket.events import event_emitter
from backend.utils.activity_logger import log_comment_activity
import re


router = APIRouter(
    prefix="/api/v1/comments",
    tags=["comments"]
)

class CommentCreate(BaseModel):
    task_id: int
    content: str

class CommentOut(BaseModel):
    comment_id: int
    user_id: int = None
    task_id: int
    content: str
    updated_at: datetime
    is_updated: int
    user_name: str = None  # 작성자 이름
    class Config:
        orm_mode = True

class CommentUpdate(BaseModel):
    content: str

@router.post("/", response_model=CommentOut)
async def create_comment(comment: CommentCreate, db: Session = Depends(get_db), current_user = Depends(verify_token)):
    db_comment = Comment(
        task_id=comment.task_id,
        user_id=current_user.user_id,
        content=comment.content,
        updated_at=datetime.now(timezone.utc),
        is_updated=0
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)

    # ActivityLog에 기록 추가
    task = db.query(Task).filter(Task.task_id == comment.task_id).first()
    if task:
        try:
            log_comment_activity(
                db=db,
                user=current_user,
                comment_id=db_comment.comment_id,
                action="create",
                project_id=task.project_id,
                task_id=task.task_id,
                comment_content=comment.content
            )
            db.commit()
        except Exception as e:
            print(f"댓글 생성 로그 작성 실패: {e}")

    # 멘션 사용자 추출 (@username 형태)
    mentioned_users = []
    mention_pattern = r'@(\w+)'
    mentions = re.findall(mention_pattern, comment.content)
    
    if mentions:
        from backend.models.user import User
        for username in mentions:
            user = db.query(User).filter(User.name == username).first()
            if user:
                mentioned_users.append(user.user_id)

    # 실시간 알림 발행
    try:
        print(f"💬 댓글 알림 발행 시작 - 댓글 ID: {db_comment.comment_id}")
        print(f"📋 Task 정보 - ID: {task.task_id}, 담당자: {task.assignee_id}, 제목: {task.title}")
        print(f"👤 작성자: {current_user.name} (ID: {current_user.user_id})")
        print(f"🏷️ 멘션된 사용자: {mentioned_users}")
        
        # 1. 태스크 담당자에게 댓글 생성 알림 (본인이 아닌 경우)
        if task and task.assignee_id and task.assignee_id != current_user.user_id:
            print(f"🔔 담당자 알림 발행 - 수신자: {task.assignee_id}")
            await create_comment_notification(
                db=db,
                user_id=task.assignee_id,
                task_id=task.task_id,
                task_title=task.title,
                comment_author=current_user.name,
                is_mention=False,
                project_id=task.project_id
            )
            print(f"✅ 담당자 알림 발행 완료")
        else:
            print(f"⏭️ 담당자 알림 생략 (담당자 없음 또는 본인)")
        
        # 2. 멘션된 사용자들에게 멘션 알림
        for mentioned_user_id in mentioned_users:
            if mentioned_user_id != current_user.user_id:  # 자기 자신 제외
                print(f"🏷️ 멘션 알림 발행 - 수신자: {mentioned_user_id}")
                await create_comment_notification(
                    db=db,
                    user_id=mentioned_user_id,
                    task_id=task.task_id,
                    task_title=task.title,
                    comment_author=current_user.name,
                    is_mention=True,
                    project_id=task.project_id
                )
                print(f"✅ 멘션 알림 발행 완료 - {mentioned_user_id}")
            else:
                print(f"⏭️ 자기 자신 멘션 생략")
        
        db.commit()  # 알림들을 DB에 저장
        print(f"💾 댓글 알림 DB 커밋 완료")
        
    except Exception as e:
        print(f"❌ 댓글 알림 발행 실패: {e}")
        import traceback
        traceback.print_exc()

    # WebSocket 이벤트 발행 (댓글 생성)
    try:
        await event_emitter.emit_comment_created(
            comment_id=db_comment.comment_id,
            task_id=comment.task_id,
            project_id=task.project_id,
            content=comment.content,
            author_id=current_user.user_id,
            author_name=current_user.name,
            mentions=mentioned_users,
            parent_comment_id=None  # 현재 대댓글 기능이 없으므로 None
        )
    except Exception as e:
        print(f"댓글 생성 WebSocket 이벤트 발행 실패: {e}")

    return db_comment

@router.get("/task/{task_id}", response_model=List[CommentOut])
def get_comments_by_task(task_id: int, db: Session = Depends(get_db)):
    from backend.models.user import User
    
    comments = db.query(Comment, User).outerjoin(
        User, Comment.user_id == User.user_id
    ).filter(Comment.task_id == task_id).order_by(Comment.updated_at.asc()).all()
    
    result = []
    for comment, user in comments:
        result.append(CommentOut(
            **comment.__dict__,
            user_name=user.name if user else "알 수 없는 사용자"
        ))
    
    return result

@router.patch("/{comment_id}", response_model=CommentOut)
async def update_comment(comment_id: int, comment: CommentUpdate, db: Session = Depends(get_db), current_user = Depends(verify_token)):
    from backend.models.user import User
    
    db_comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    
    # 권한 체크: 댓글 작성자만 수정 가능
    if db_comment.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="댓글 작성자만 수정할 수 있습니다.")
    
    db_comment.content = comment.content
    db_comment.is_updated = 1
    db_comment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_comment)
    
    # ActivityLog에 기록 추가
    task = db.query(Task).filter(Task.task_id == db_comment.task_id).first()
    if task:
        try:
            log_comment_activity(
                db=db,
                user=current_user,
                comment_id=db_comment.comment_id,
                action="update",
                project_id=task.project_id,
                task_id=task.task_id,
                comment_content=comment.content
            )
            db.commit()
        except Exception as e:
            print(f"댓글 수정 로그 작성 실패: {e}")
    
    # WebSocket 이벤트 발행 (댓글 수정)
    try:
        # Task 정보 조회
        task = db.query(Task).filter(Task.task_id == db_comment.task_id).first()
        if task:
            await event_emitter.emit_comment_updated(
                comment_id=db_comment.comment_id,
                task_id=db_comment.task_id,
                project_id=task.project_id,
                content=db_comment.content,
                author_id=current_user.user_id,
                author_name=current_user.name
            )
    except Exception as e:
        print(f"댓글 수정 WebSocket 이벤트 발행 실패: {e}")
    
    # 사용자 정보 포함하여 응답
    user = db.query(User).filter(User.user_id == db_comment.user_id).first()
    return CommentOut(
        **db_comment.__dict__,
        user_name=user.name if user else "알 수 없는 사용자"
    )

@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: int, db: Session = Depends(get_db), current_user = Depends(verify_token)):
    db_comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    
    # 권한 체크: 댓글 작성자만 삭제 가능
    if db_comment.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="댓글 작성자만 삭제할 수 있습니다.")
    
    # 삭제 전에 정보 저장 (WebSocket 이벤트용)
    comment_info = {
        "comment_id": db_comment.comment_id,
        "task_id": db_comment.task_id
    }
    
    # Task 정보 조회
    task = db.query(Task).filter(Task.task_id == db_comment.task_id).first()
    
    # ActivityLog에 기록 추가 (삭제 전에)
    if task:
        try:
            log_comment_activity(
                db=db,
                user=current_user,
                comment_id=db_comment.comment_id,
                action="delete",
                project_id=task.project_id,
                task_id=task.task_id,
                comment_content=db_comment.content
            )
            db.commit()
        except Exception as e:
            print(f"댓글 삭제 로그 작성 실패: {e}")
    
    db.delete(db_comment)
    db.commit()
    
    # WebSocket 이벤트 발행 (댓글 삭제)
    try:
        if task:
            await event_emitter.emit_comment_deleted(
                comment_id=comment_info["comment_id"],
                task_id=comment_info["task_id"],
                project_id=task.project_id,
                deleted_by=current_user.user_id
            )
    except Exception as e:
        print(f"댓글 삭제 WebSocket 이벤트 발행 실패: {e}")
    
    return None 