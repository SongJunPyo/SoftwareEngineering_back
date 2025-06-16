from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database.base import get_db
from backend.models.logs_notification import Notification
from backend.models.user import User
from backend.middleware.auth import verify_token

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

async def create_notification(
    db: Session,
    user_id: int,
    type: str,
    message: str,
    channel: str,
    related_id: int = None
):
    notification = Notification(
        user_id=user_id,
        type=type,
        message=message,
        channel=channel,
        is_read=False,
        related_id=related_id
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

@router.get("/")
async def get_notifications(
    page: int = 1,
    per_page: int = 10,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # 페이지네이션 계산
    offset = (page - 1) * per_page
    
    notifications = db.query(Notification)\
        .filter(Notification.user_id == current_user.user_id)\
        .order_by(Notification.created_at.desc())\
        .offset(offset)\
        .limit(per_page)\
        .all()
    print(db.query(Notification).all())
    total = db.query(Notification)\
        .filter(Notification.user_id == current_user.user_id)\
        .count()

    return {
        "items": [n.to_dict() for n in notifications],
        "total": total
    }

@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    notification = db.query(Notification)\
        .filter(Notification.notification_id == notification_id)\
        .first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    
    return {"result": "success"}