from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.base import get_db
from backend.models.comment_file import Comment
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
from backend.middleware.auth import verify_token

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
    class Config:
        orm_mode = True

class CommentUpdate(BaseModel):
    content: str

@router.post("/", response_model=CommentOut)
def create_comment(comment: CommentCreate, db: Session = Depends(get_db), current_user = Depends(verify_token)):
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
    return db_comment

@router.get("/task/{task_id}", response_model=List[CommentOut])
def get_comments_by_task(task_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.task_id == task_id).order_by(Comment.updated_at.asc()).all()
    return comments

@router.patch("/{comment_id}", response_model=CommentOut)
def update_comment(comment_id: int, comment: CommentUpdate, db: Session = Depends(get_db), current_user = Depends(verify_token)):
    db_comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    db_comment.content = comment.content
    db_comment.is_updated = 1
    db_comment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_comment)
    return db_comment

@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: Session = Depends(get_db), current_user = Depends(verify_token)):
    db_comment = db.query(Comment).filter(Comment.comment_id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    db.delete(db_comment)
    db.commit()
    return None 