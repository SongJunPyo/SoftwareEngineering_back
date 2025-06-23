from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_, or_, func
from typing import List, Optional
from datetime import datetime, timedelta

from backend.database.base import get_db
from backend.models.logs_notification import ActivityLog, LogResponse
from backend.models.user import User
from backend.models.project import ProjectMember
from backend.middleware.auth import verify_token
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])

class LogStats(BaseModel):
    period_days: int
    total_activities: int
    action_stats: List[dict]
    entity_stats: List[dict]
    top_users: List[dict]

@router.get("/{project_id}", response_model=List[LogResponse])
def get_project_logs(
    project_id: int,
    limit: int = Query(50, ge=1, le=100, description="한 번에 가져올 로그 수"),
    offset: int = Query(0, ge=0, description="건너뛸 로그 수"),
    entity_type: Optional[str] = Query(None, description="엔티티 타입 필터"),
    action: Optional[str] = Query(None, description="액션 필터"), 
    user_id: Optional[int] = Query(None, description="사용자 ID 필터"),
    start_date: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="검색어"),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트의 활동 로그를 가져옵니다."""
    
    # 1. 권한 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="프로젝트 접근 권한이 없습니다.")

    # 2. 기본 쿼리 구성
    query = db.query(ActivityLog).filter(ActivityLog.project_id == project_id)

    # 3. 필터 적용
    if entity_type:
        query = query.filter(ActivityLog.entity_type == entity_type)
    
    if action:
        query = query.filter(ActivityLog.action == action)
    
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)
    
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(ActivityLog.timestamp >= start_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="잘못된 시작 날짜 형식입니다.")
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(ActivityLog.timestamp < end_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="잘못된 종료 날짜 형식입니다.")
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                ActivityLog.user_name.ilike(search_term),
                ActivityLog.details.ilike(search_term),
                ActivityLog.action.ilike(search_term)
            )
        )

    # 4. 정렬 및 페이지네이션
    logs = query.order_by(desc(ActivityLog.timestamp)).offset(offset).limit(limit).all()
    
    # 5. user_name이 없는 로그의 경우 user_id로 사용자 정보 조회
    for log in logs:
        if not log.user_name and log.user_id:
            user = db.query(User).filter(User.user_id == log.user_id).first()
            if user:
                log.user_name = user.name
    
    return logs

@router.get("/{project_id}/stats", response_model=LogStats)
def get_log_stats(
    project_id: int,
    days: int = Query(7, ge=1, le=30, description="통계 기간 (일)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트의 활동 통계를 가져옵니다."""
    
    # 1. 권한 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="프로젝트 접근 권한이 없습니다.")

    # 2. 날짜 범위 설정
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # 3. 기본 통계
    total_activities = db.query(ActivityLog).filter(
        ActivityLog.project_id == project_id,
        ActivityLog.timestamp >= start_date
    ).count()
    
    # 4. 액션별 통계
    action_stats = db.query(
        ActivityLog.action,
        func.count(ActivityLog.log_id).label('count')
    ).filter(
        ActivityLog.project_id == project_id,
        ActivityLog.timestamp >= start_date
    ).group_by(ActivityLog.action).all()
    
    # 5. 엔티티 타입별 통계
    entity_stats = db.query(
        ActivityLog.entity_type,
        func.count(ActivityLog.log_id).label('count')
    ).filter(
        ActivityLog.project_id == project_id,
        ActivityLog.timestamp >= start_date
    ).group_by(ActivityLog.entity_type).all()
    
    # 6. 사용자별 활동 통계
    user_stats = db.query(
        ActivityLog.user_name,
        func.count(ActivityLog.log_id).label('count')
    ).filter(
        ActivityLog.project_id == project_id,
        ActivityLog.timestamp >= start_date,
        ActivityLog.user_name.isnot(None)
    ).group_by(ActivityLog.user_name).order_by(desc('count')).limit(5).all()
    
    return LogStats(
        period_days=days,
        total_activities=total_activities,
        action_stats=[{"action": action, "count": count} for action, count in action_stats],
        entity_stats=[{"entity_type": entity_type, "count": count} for entity_type, count in entity_stats],
        top_users=[{"user_name": user_name, "count": count} for user_name, count in user_stats]
    )

@router.get("/{project_id}/recent", response_model=List[LogResponse])
def get_recent_logs(
    project_id: int,
    limit: int = Query(10, ge=1, le=50, description="최근 로그 수"),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트의 최근 활동 로그를 가져옵니다."""
    
    # 1. 권한 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="프로젝트 접근 권한이 없습니다.")

    # 2. 최근 로그 조회
    logs = db.query(ActivityLog).filter(
        ActivityLog.project_id == project_id
    ).order_by(desc(ActivityLog.timestamp)).limit(limit).all()
    
    # 3. user_name이 없는 로그의 경우 user_id로 사용자 정보 조회
    for log in logs:
        if not log.user_name and log.user_id:
            user = db.query(User).filter(User.user_id == log.user_id).first()
            if user:
                log.user_name = user.name
    
    return logs

# 기존 API 유지 (하위 호환성)
@router.get("/", response_model=List[LogResponse])
def get_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """모든 로그를 조회합니다 (관리자용)."""
    logs = db.query(ActivityLog).offset(skip).limit(limit).all()
    return logs

@router.get("/log/{log_id}", response_model=LogResponse)
def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """특정 로그를 조회합니다."""
    log = db.query(ActivityLog).filter(ActivityLog.log_id == log_id).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return log