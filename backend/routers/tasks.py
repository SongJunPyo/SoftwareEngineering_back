from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from backend.database.base import get_db
from backend.models.task import Task, TaskMember
from backend.models.user import User
from backend.middleware.auth import verify_token
from backend.routers.notifications import create_notification

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

@router.post("/")
async def create_task(
    title: str,
    description: str,
    due_date: datetime,
    project_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    task = Task(
        title=title,
        description=description,
        due_date=due_date,
        project_id=project_id,
        user_id=current_user.user_id
    )
    db.add(task)
    db.commit()
    db.refresh(task)



    return task 