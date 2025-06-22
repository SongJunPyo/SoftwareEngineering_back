from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Dict, Optional

from backend.database.base import get_db
from backend.models.task import Task
from backend.models.user import User
from backend.models.project import ProjectMember
from backend.models.tag import Tag
from backend.models.tag import TaskTag
from backend.models.logs_notification import Notification
from backend.middleware.auth import verify_token
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

# --- Pydantic 모델 정의 ---
class StatusOverview(BaseModel):
    total_tasks: int
    todo: int
    in_progress: int
    complete: int

class TagUsage(BaseModel):
    tag_name: str
    count: int
    
class TeamWorkload(BaseModel):
    member_name: str
    task_count: int

class RecentActivity(BaseModel):
    message: str
    created_at: str

class ParentTaskProgress(BaseModel):
    progress: float
    total_parent_tasks: int
    completed_parent_tasks: int
    
class DashboardData(BaseModel):
    status_overview: StatusOverview
    personal_overview: StatusOverview
    recent_activities: List[RecentActivity]
    tag_usage: List[TagUsage]
    team_workload: List[TeamWorkload]
    parent_task_progress: ParentTaskProgress

# --- API 엔드포인트 ---
@router.get("/{project_id}", response_model=DashboardData)
def get_dashboard_data(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    # 1. 권한 확인
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="프로젝트 접근 권한이 없습니다.")

    # 2. 기본 업무 데이터 조회
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    total_tasks = len(tasks)

    # --- 데이터 계산 ---
    
    # 2.1 전체 상태 개요
    status_overview = {
        "total_tasks": total_tasks,
        "todo": sum(1 for t in tasks if t.status == 'todo'),
        "in_progress": sum(1 for t in tasks if t.status == 'In progress'),
        "complete": sum(1 for t in tasks if t.status == 'complete')
    }

    # 2.2 개인 상태 개요
    my_tasks = [t for t in tasks if t.assignee_id == current_user.user_id]
    personal_overview = {
        "total_tasks": len(my_tasks),
        "todo": sum(1 for t in my_tasks if t.status == 'todo'),
        "in_progress": sum(1 for t in my_tasks if t.status == 'In progress'),
        "complete": sum(1 for t in my_tasks if t.status == 'complete')
    }

    # 2.3 최근 활동 (알림 기반)
    activities_query = db.query(Notification).filter(
        Notification.user_id.in_(
            db.query(ProjectMember.user_id).filter(ProjectMember.project_id == project_id)
        )
    ).order_by(desc(Notification.created_at)).limit(5).all()
    recent_activities = [{"message": a.message, "created_at": a.created_at.isoformat()} for a in activities_query]


    # 2.4 태그 유형
    tag_usage_query = db.query(
        Tag.tag_name, func.count(TaskTag.task_id).label('count')
    ).join(TaskTag, Tag.tag_name == TaskTag.tag_name)\
     .join(Task, TaskTag.task_id == Task.task_id)\
     .filter(Task.project_id == project_id)\
     .group_by(Tag.tag_name)\
     .order_by(desc('count'))\
     .limit(5).all()
    tag_usage = [{"tag_name": name, "count": count} for name, count in tag_usage_query]

    # 2.5 팀 워크로드
    workload_query = db.query(
        User.name, func.count(Task.task_id).label('task_count')
    ).join(Task, User.user_id == Task.assignee_id)\
     .filter(Task.project_id == project_id, Task.assignee_id != None)\
     .group_by(User.name)\
     .order_by(desc('task_count'))\
     .all()
    team_workload = [{"member_name": name, "task_count": count} for name, count in workload_query]

    # 2.6 상위 업무 진행률
    parent_tasks = [t for t in tasks if t.is_parent_task]
    total_parent_tasks = len(parent_tasks)
    completed_parent_tasks = 0
    if total_parent_tasks > 0:
        for p_task in parent_tasks:
            child_tasks = db.query(Task).filter(Task.parent_task_id == p_task.task_id).all()
            if not child_tasks: # 하위 업무가 없으면 100% 완료로 간주
                completed_parent_tasks += 1
                continue
            if all(ct.status == 'complete' for ct in child_tasks):
                completed_parent_tasks += 1
        parent_progress = (completed_parent_tasks / total_parent_tasks) * 100 if total_parent_tasks > 0 else 0
    else:
        parent_progress = 0
        
    parent_task_progress = {
        "progress": parent_progress,
        "total_parent_tasks": total_parent_tasks,
        "completed_parent_tasks": completed_parent_tasks
    }
    
    return DashboardData(
        status_overview=status_overview,
        personal_overview=personal_overview,
        recent_activities=recent_activities,
        tag_usage=tag_usage,
        team_workload=team_workload,
        parent_task_progress=parent_task_progress
    ) 