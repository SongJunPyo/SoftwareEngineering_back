from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, or_
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date

from backend.database.base import get_db
from backend.models.task import Task
from backend.models.task_tag import TaskTag
from backend.models.tag import Tag
from backend.models.user import User
from backend.models.project import ProjectMember
from backend.middleware.auth import verify_token
from backend.routers.notifications import create_notification


router = APIRouter(prefix="/api/v1", tags=["tasks"])

class TaskCreate(BaseModel):
    title: str
    project_id: int
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    assignee_id: Optional[int] = None
    parent_task_id: Optional[int] = None
    is_parent_task: bool = False
    priority: str = 'medium'
    tag_names: List[str] = []
    status: str = 'todo'

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    assignee_id: Optional[int] = None
    parent_task_id: Optional[int] = None
    is_parent_task: Optional[bool] = None
    priority: Optional[str] = None
    tag_names: Optional[List[str]] = None
    status: Optional[str] = None
    description: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: int
    title: str
    project_id: int
    created_at: datetime
    updated_at: datetime
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None

    parent_task_id: Optional[int] = None
    parent_task_title: Optional[str] = None
    
    is_parent_task: bool
    priority: str
    status: str
    description: Optional[str] = None
    
    tag_names: List[str] = []

    class Config:
        orm_mode = True

@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks_for_project(
    project_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(verify_token)
):
    # 1. 권한 확인: 현재 유저가 해당 프로젝트의 멤버인지 확인
    member_check = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()

    if not member_check:
        raise HTTPException(status_code=403, detail="프로젝트에 접근할 권한이 없습니다.")
    
    # 2. 작업 목록 조회
    tasks = db.query(Task).filter(Task.project_id == project_id).options(
        joinedload(Task.assignee),
        joinedload(Task.parent_task),
        joinedload(Task.tags).joinedload(TaskTag.tag)
    ).order_by(desc(Task.created_at)).all()

    # 3. 응답 데이터 가공
    response_data = []
    for task in tasks:
        tag_names = [task_tag.tag.name for task_tag in task.tags]
        
        response_data.append(
            TaskResponse(
                task_id=task.task_id,
                title=task.title,
                project_id=task.project_id,
                created_at=task.created_at,
                updated_at=task.updated_at,
                start_date=task.start_date,
                due_date=task.due_date,
                assignee_id=task.assignee_id,
                assignee_name=task.assignee.name if task.assignee else None,
                parent_task_id=task.parent_task_id,
                parent_task_title=task.parent_task.title if task.parent_task else None,
                is_parent_task=task.is_parent_task,
                priority=task.priority,
                status=task.status,
                description=task.description,
                tag_names=tag_names,
            )
        )
    return response_data

@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    # 권한 확인
    member_check = db.query(ProjectMember).filter(
        ProjectMember.project_id == task_data.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()

    if not member_check or member_check.role == 'viewer':
        raise HTTPException(status_code=403, detail="업무를 생성할 권한이 없습니다.")

    # 담당자 유효성 확인
    if task_data.assignee_id:
        assignee_member = db.query(ProjectMember).filter(
            ProjectMember.project_id == task_data.project_id,
            ProjectMember.user_id == task_data.assignee_id
        ).first()
        if not assignee_member:
            raise HTTPException(status_code=404, detail="지정한 담당자가 프로젝트 멤버가 아닙니다.")
            
    # 새 작업 생성
    new_task = Task(
        title=task_data.title,
        project_id=task_data.project_id,
        start_date=task_data.start_date,
        due_date=task_data.due_date,
        assignee_id=task_data.assignee_id,
        parent_task_id=task_data.parent_task_id,
        is_parent_task=task_data.is_parent_task,
        priority=task_data.priority,
        status=task_data.status
    )
    db.add(new_task)
    db.flush() 

    # 태그 처리
    if task_data.tag_names:
        for tag_name in task_data.tag_names:
            tag = db.query(Tag).filter(Tag.name == tag_name, Tag.project_id == task_data.project_id).first()
            if not tag:
                tag = Tag(name=tag_name, project_id=task_data.project_id)
                db.add(tag)
                db.flush()
            task_tag = TaskTag(task_id=new_task.task_id, tag_id=tag.tag_id)
            db.add(task_tag)
    
    # 알림 생성 (담당자가 지정되었고, 본인이 아닌 경우)
    if task_data.assignee_id and task_data.assignee_id != current_user.user_id:
        await create_notification(
            db=db,
            user_id=task_data.assignee_id,
            type='task',
            message=f"'{new_task.title}' 업무의 담당자로 지정되었습니다.",
            channel='task',
            related_id=new_task.task_id
        )

    db.commit()
    db.refresh(new_task)

    # 응답을 위해 상세 정보 다시 로드
    task_with_details = db.query(Task).filter(Task.task_id == new_task.task_id).options(
        joinedload(Task.assignee),
        joinedload(Task.parent_task),
        joinedload(Task.tags).joinedload(TaskTag.tag)
    ).one()

    tag_names = [task_tag.tag.name for task_tag in task_with_details.tags]
    return TaskResponse(
        task_id=task_with_details.task_id,
        title=task_with_details.title,
        project_id=task_with_details.project_id,
        created_at=task_with_details.created_at,
        updated_at=task_with_details.updated_at,
        start_date=task_with_details.start_date,
        due_date=task_with_details.due_date,
        assignee_id=task_with_details.assignee_id,
        assignee_name=task_with_details.assignee.name if task_with_details.assignee else None,
        parent_task_id=task_with_details.parent_task_id,
        parent_task_title=task_with_details.parent_task.title if task_with_details.parent_task else None,
        is_parent_task=task_with_details.is_parent_task,
        priority=task_with_details.priority,
        status=task_with_details.status,
        description=task_with_details.description,
        tag_names=tag_names,
    )

@router.get("/parent-tasks", response_model=List[TaskResponse])
async def get_parent_tasks(
    project_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(verify_token)
):
    # 권한 확인
    member_check = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member_check:
        raise HTTPException(status_code=403, detail="프로젝트에 접근할 권한이 없습니다.")

    parent_tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.is_parent_task == True
    ).all()
    
    return [
        TaskResponse(
            task_id=task.task_id,
            title=task.title,
            project_id=task.project_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            start_date=task.start_date,
            due_date=task.due_date,
            assignee_id=task.assignee_id,
            assignee_name=task.assignee.name if task.assignee else None,
            parent_task_id=task.parent_task_id,
            parent_task_title=None,
            is_parent_task=task.is_parent_task,
            priority=task.priority,
            status=task.status,
            description=task.description,
            tag_names=[]
        ) for task in parent_tasks
    ]

@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(verify_token)
):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다.")

    # 프로젝트 멤버 여부 확인
    member_check = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()

    if not member_check:
        raise HTTPException(status_code=403, detail="프로젝트에 접근할 권한이 없습니다.")

    # 태스크 담당자 또는 프로젝트 관리자/편집자만 삭제 가능
    if task.assignee_id != current_user.user_id and member_check.role not in ['admin', 'editor']:
         raise HTTPException(status_code=403, detail="태스크를 삭제할 권한이 없습니다.")

    # 하위 태스크가 있는 경우 삭제 불가
    if db.query(Task).filter(Task.parent_task_id == task_id).first():
        raise HTTPException(status_code=400, detail="하위 업무가 있는 상위 업무는 삭제할 수 없습니다.")
    
    db.query(TaskTag).filter(TaskTag.task_id == task_id).delete()
    db.delete(task)
    db.commit()
    return

@router.patch("/tasks/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: int,
    status_update: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="업무를 찾을 수 없습니다.")

    # 권한 확인 (뷰어 제외)
    member_check = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not member_check or member_check.role == 'viewer':
        raise HTTPException(status_code=403, detail="상태를 변경할 권한이 없습니다.")

    new_status = status_update.get("status")
    # 프론트엔드 상태값을 지원하도록 업데이트
    valid_frontend_statuses = ['todo', 'in_progress', 'pending', 'complete']
    if new_status not in valid_frontend_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"유효하지 않은 상태 값입니다. 다음 중 하나여야 합니다: {', '.join(valid_frontend_statuses)}"
        )

    task.status = new_status
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    # 응답 데이터 가공
    task_with_details = db.query(Task).filter(Task.task_id == task_id).options(
        joinedload(Task.assignee),
        joinedload(Task.parent_task),
        joinedload(Task.tags).joinedload(TaskTag.tag)
    ).one()
    
    tag_names = [task_tag.tag.name for task_tag in task_with_details.tags]

    return TaskResponse(
        task_id=task_with_details.task_id,
        title=task_with_details.title,
        project_id=task_with_details.project_id,
        created_at=task_with_details.created_at,
        updated_at=task_with_details.updated_at,
        start_date=task_with_details.start_date,
        due_date=task_with_details.due_date,
        assignee_id=task_with_details.assignee_id,
        assignee_name=task_with_details.assignee.name if task_with_details.assignee else None,
        parent_task_id=task_with_details.parent_task_id,
        parent_task_title=task_with_details.parent_task.title if task_with_details.parent_task else None,
        is_parent_task=task_with_details.is_parent_task,
        priority=task_with_details.priority,
        status=task_with_details.status,
        description=task_with_details.description,
        tag_names=tag_names,
    )
