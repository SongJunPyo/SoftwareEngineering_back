from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.base import get_db
from backend.models.comment_file import Comment
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
from backend.middleware.auth import verify_token
from backend.models.task import Task
from backend.routers.notifications import create_notification
from backend.models.logs_notification import ActivityLog


router = APIRouter(
    prefix="/comments",
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
        log = ActivityLog(
            user_id=current_user.user_id,
            entity_type="comment",
            entity_id=db_comment.comment_id,
            action="create",
            project_id=task.project_id
        )
        db.add(log)
        db.commit()

    # 태스크 담당자에게 알림 생성
    if task and task.assignee_id != current_user.user_id:  # 담당자가 댓글 작성자가 아닌 경우에만
        await create_notification(
            db=db,
            user_id=task.assignee_id,
            type="comment",
            message=f"{current_user.name}님이 태스크에 댓글을 남겼습니다.",
            channel="task",
            related_id=task.task_id
        )

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
def update_comment(comment_id: int, comment: CommentUpdate, db: Session = Depends(get_db), current_user = Depends(verify_token)):
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
    
    # 사용자 정보 포함하여 응답
    user = db.query(User).filter(User.user_id == db_comment.user_id).first()
    return CommentOut(
        **db_comment.__dict__,
        user_name=user.name if user else "알 수 없는 사용자"
    )

@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: Session = Depends(get_db), current_user = Depends(verify_token)):
    db_comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    
    # 권한 체크: 댓글 작성자만 삭제 가능
    if db_comment.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="댓글 작성자만 삭제할 수 있습니다.")
    
    db.delete(db_comment)
    db.commit()
    return None 