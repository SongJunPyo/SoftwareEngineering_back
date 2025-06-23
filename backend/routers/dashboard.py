from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Dict, Optional

from backend.database.base import get_db
from backend.models.task import Task
from backend.models.user import User
from backend.models.project import ProjectMember
from backend.models.tag import Tag, TaskTag
from backend.models.logs_notification import Notification
from backend.middleware.auth import verify_token
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

# --- Pydantic 모델 정의 ---
class StatusOverview(BaseModel):
    total_tasks: int
    todo: int
    in_progress: int
    pending: int
    complete: int

class TagUsage(BaseModel):
    tag_name: str
    total_count: int
    todo: int
    in_progress: int
    pending: int
    complete: int
    
class TeamWorkload(BaseModel):
    member_name: str
    total_count: int
    todo: int
    in_progress: int
    pending: int
    complete: int

class RecentActivity(BaseModel):
    message: str
    created_at: str

class ParentTaskProgress(BaseModel):
    parent_task_name: str
    total_count: int
    todo: int
    in_progress: int
    pending: int
    complete: int
    
class DashboardData(BaseModel):
    status_overview: StatusOverview
    personal_overview: StatusOverview
    recent_activities: List[RecentActivity]
    tag_usage: List[TagUsage]
    team_workload: List[TeamWorkload]
    parent_task_progress: List[ParentTaskProgress]

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

    # 2. 기본 업무 데이터 조회 (태그 정보 및 담당자 정보 포함)
    tasks = db.query(Task).options(joinedload(Task.assignee)).filter(Task.project_id == project_id).all()
    
    # 각 업무의 태그 정보를 미리 로드
    task_tags = {}
    for task in tasks:
        tags = db.query(TaskTag).filter(TaskTag.task_id == task.task_id).all()
        task_tags[task.task_id] = [tag.tag_name for tag in tags]
    
    total_tasks = len(tasks)

    # --- 데이터 계산 ---
    
    # 2.1 전체 상태 개요
    status_overview = {
        "total_tasks": total_tasks,
        "todo": sum(1 for t in tasks if t.status == 'todo'),
        "in_progress": sum(1 for t in tasks if t.status == 'in_progress'),
        "pending": sum(1 for t in tasks if t.status == 'pending'),
        "complete": sum(1 for t in tasks if t.status == 'complete')
    }

    # 2.2 개인 상태 개요
    my_tasks = [t for t in tasks if t.assignee_id == current_user.user_id]
    personal_overview = {
        "total_tasks": len(my_tasks),
        "todo": sum(1 for t in my_tasks if t.status == 'todo'),
        "in_progress": sum(1 for t in my_tasks if t.status == 'in_progress'),
        "pending": sum(1 for t in my_tasks if t.status == 'pending'),
        "complete": sum(1 for t in my_tasks if t.status == 'complete')
    }

    # 2.3 최근 활동 (알림 기반)
    activities_query = db.query(Notification).filter(
        Notification.user_id.in_(
            db.query(ProjectMember.user_id).filter(ProjectMember.project_id == project_id)
        )
    ).order_by(desc(Notification.created_at)).limit(5).all()
    recent_activities = [{"message": a.message, "created_at": a.created_at.isoformat()} for a in activities_query]


    # 2.4 태그 유형 (상태별 집계)
    tag_usage = []
    tag_list = db.query(Tag.tag_name).filter(Tag.project_id == project_id).all()
    for tag_row in tag_list:
        tag_name = tag_row.tag_name
        # 해당 태그를 가진 업무들 찾기
        tag_tasks = [t for t in tasks if tag_name in task_tags.get(t.task_id, [])]
        if tag_tasks:  # 태그가 사용된 경우만 포함
            tag_usage.append({
                "tag_name": tag_name,
                "total_count": len(tag_tasks),
                "todo": sum(1 for t in tag_tasks if t.status == 'todo'),
                "in_progress": sum(1 for t in tag_tasks if t.status == 'in_progress'),
                "pending": sum(1 for t in tag_tasks if t.status == 'pending'),
                "complete": sum(1 for t in tag_tasks if t.status == 'complete')
            })
    tag_usage.sort(key=lambda x: x['total_count'], reverse=True)
    tag_usage = tag_usage[:5]  # 상위 5개만

    # 2.5 팀 워크로드 (상태별 집계)
    team_workload = []
    assigned_tasks = [t for t in tasks if t.assignee_id is not None and t.assignee is not None]
    member_dict = {}
    for task in assigned_tasks:
        member_name = task.assignee.name
        if member_name not in member_dict:
            member_dict[member_name] = []
        member_dict[member_name].append(task)
    
    for member_name, member_tasks in member_dict.items():
        team_workload.append({
            "member_name": member_name,
            "total_count": len(member_tasks),
            "todo": sum(1 for t in member_tasks if t.status == 'todo'),
            "in_progress": sum(1 for t in member_tasks if t.status == 'in_progress'),
            "pending": sum(1 for t in member_tasks if t.status == 'pending'),
            "complete": sum(1 for t in member_tasks if t.status == 'complete')
        })
    team_workload.sort(key=lambda x: x['total_count'], reverse=True)

    # 2.6 상위 업무 진행률 (각 상위 업무별 하위 업무 상태 집계)
    parent_tasks = [t for t in tasks if t.is_parent_task]
    parent_task_progress = []
    
    for parent_task in parent_tasks:
        # 해당 상위 업무의 하위 업무들 찾기
        child_tasks = [t for t in tasks if t.parent_task_id == parent_task.task_id]
        
        # 하위 업무가 없으면 상위 업무 자체의 상태만 고려
        if not child_tasks:
            child_tasks = [parent_task]
        
        parent_task_progress.append({
            "parent_task_name": parent_task.title,
            "total_count": len(child_tasks),
            "todo": sum(1 for t in child_tasks if t.status == 'todo'),
            "in_progress": sum(1 for t in child_tasks if t.status == 'in_progress'),
            "pending": sum(1 for t in child_tasks if t.status == 'pending'),
            "complete": sum(1 for t in child_tasks if t.status == 'complete')
        })
    
    # 하위 업무 개수 기준으로 정렬
    parent_task_progress.sort(key=lambda x: x['total_count'], reverse=True)
    parent_task_progress = parent_task_progress[:5]  # 상위 5개만
    
    return DashboardData(
        status_overview=status_overview,
        personal_overview=personal_overview,
        recent_activities=recent_activities,
        tag_usage=tag_usage,
        team_workload=team_workload,
        parent_task_progress=parent_task_progress
    ) 