print("LOGS MODULE LOADED")
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.database.base import get_db
print("LOGS MODULE LOADED2")
from backend.models.logs_notification import ActivityLog
print("LOGS MODULE LOADED3")
from backend.schemas.log import LogResponse
print("LOGS MODULE LOADED4")
router = APIRouter(
    prefix="/api/v1/logs",
    tags=["logs"]
)

@router.get("/", response_model=List[LogResponse])
def get_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    모든 로그를 조회합니다.
    """
    
    print(ActivityLog)  
    logs = db.query(ActivityLog).offset(skip).limit(limit).all()
    print(logs)
    print("22222222")
    return logs

@router.get("/{log_id}", response_model=LogResponse)
def get_log(
    log_id: int,
    db: Session = Depends(get_db)
):
    """
    특정 로그를 조회합니다.
    """
    log = db.query(ActivityLog).filter(ActivityLog.log_id == log_id).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return log 