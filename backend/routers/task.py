from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import asyncio

from backend.database.base import get_db
from backend.middleware.auth import verify_token
from backend.models.task import Task as TaskModel
from backend.models.task import TaskMember
from backend.models.project import Project, ProjectMember
from backend.schemas.Task import TaskCreateRequest, TaskUpdateRequest, TaskResponse

router = APIRouter(prefix="/api/v1")

@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_task(
    task_in: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    # 1) 프로젝트 유효성 검증
    project = db.query(Project).filter_by(
        project_id=task_in.project_id
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # 2) (선택) 상위 업무 유효성 검증
    if task_in.parent_task_id is not None:
        parent = db.query(TaskModel).filter_by(
            task_id=task_in.parent_task_id
        ).first()
        if not parent:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent task not found")

    now = datetime.now(timezone.utc)
    start_date = task_in.start_date
    due_date = task_in.due_date

    # start_date, due_date가 문자열이면 datetime으로 변환 (항상 UTC로)
    def to_aware(dt):
        if isinstance(dt, str):
            d = datetime.fromisoformat(dt)
        else:
            d = dt
        if d.tzinfo is None:
            # 타임존 정보 없으면 UTC로 지정
            d = d.replace(tzinfo=timezone.utc)
        return d

    start_date = to_aware(task_in.start_date)
    due_date = to_aware(task_in.due_date)

    if now < start_date:
        status_value = "todo"
    elif start_date <= now <= due_date:
        status_value = "In progress"
    else:
        status_value = "complete"

    # 3) tasks 테이블에 새 업무 저장 (assignee_id는 프론트에서 받은 값 사용)
    task = TaskModel(
        title           = task_in.title,
        project_id      = task_in.project_id,
        parent_task_id  = task_in.parent_task_id,
        start_date      = task_in.start_date,
        due_date        = task_in.due_date,
        priority        = task_in.priority,
        assignee_id     = task_in.assignee_id,
        status          = status_value,  # status 필드 자동 설정
        is_parent_task  = task_in.is_parent_task,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 4) task_members 테이블에 매핑 추가 (project_id, user_id, assigned_at)
    if task_in.assignee_id is not None:
        mapping = TaskMember(
            task_id     = task.task_id,
            user_id     = task_in.assignee_id,
        )
        db.add(mapping)
    db.commit()
    
    
    # 5) 생성된 Task 객체를 반환 (TaskOut 직렬화)
    return task

@router.get("/tasks", response_model=List[TaskResponse])
def read_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    tasks = (
        db.query(TaskModel)
          .filter(TaskModel.project_id == project_id)
          .all()
    )
    
    result = []
    for task in tasks:
        # task_members 조회
        task_members = db.query(TaskMember).filter(TaskMember.task_id == task.task_id).all()
        member_ids = [tm.user_id for tm in task_members]
        
        # 상위 업무 제목 조회
        parent_task_title = None
        if task.parent_task_id:
            parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
            parent_task_title = parent_task.title if parent_task else None
        
        result.append(TaskResponse(
            **task.__dict__,
            assignee_name=task.assignee.name if task.assignee else None,
            parent_task_title=parent_task_title,
            member_ids=member_ids
        ))
    
    return result

# 1) 단일 Task 조회 엔드포인트
@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK
)
def read_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # task_members 조회
    task_members = db.query(TaskMember).filter(TaskMember.task_id == task_id).all()
    member_ids = [tm.user_id for tm in task_members]

    # 상위 업무 제목 조회
    parent_task_title = None
    if task.parent_task_id:
        parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
        parent_task_title = parent_task.title if parent_task else None

    return TaskResponse(
        **task.__dict__,
        assignee_name=task.assignee.name if task.assignee else None,
        parent_task_title=parent_task_title,
        member_ids=member_ids
    )


# 2) Task 업데이트 엔드포인트 (title, assignee, members, status 등 수정 가능)
@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK
)
async def update_task(
    task_id: int,
    task_update: TaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # 권한 검증: Task의 담당자 또는 프로젝트 멤버만 수정 가능
    project_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if task.assignee_id != current_user.user_id and not project_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="해당 Task의 담당자 또는 프로젝트 멤버만 수정할 수 있습니다"
        )
    
    updated = False
    
    # 업데이트 가능한 필드들 처리
    update_data = task_update.dict(exclude_unset=True, exclude={'member_ids'})
    
    for field, new_value in update_data.items():
        if field in ['start_date', 'due_date'] and new_value:
            # 날짜 필드 처리
            if isinstance(new_value, str):
                from datetime import datetime, timezone, date
                try:
                    # YYYY-MM-DD 형식을 date 객체로 변환
                    new_value = datetime.strptime(new_value, '%Y-%m-%d').date()
                except ValueError:
                    # 다른 형식이면 datetime으로 파싱 후 date로 변환
                    if len(new_value) == 10:  # YYYY-MM-DD 형식
                        new_value = new_value + 'T00:00:00'
                    dt = datetime.fromisoformat(new_value)
                    new_value = dt.date()
            elif isinstance(new_value, datetime):
                new_value = new_value.date()
        
        # 기존 값과 다른 경우에만 업데이트
        if getattr(task, field) != new_value:
            setattr(task, field, new_value)
            updated = True
    
    # 업무 멤버 업데이트 처리
    if task_update.member_ids is not None:
        # 기존 task_members 삭제
        db.query(TaskMember).filter(TaskMember.task_id == task_id).delete()
        
        # 새로운 task_members 추가
        for user_id in task_update.member_ids:
            task_member = TaskMember(task_id=task_id, user_id=user_id)
            db.add(task_member)
        
        updated = True
    
    if updated:
        # updated_at은 onupdate로 자동 설정되지만 명시적으로 설정
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
    
    # 응답에 member_ids와 parent_task_title 포함
    task_members = db.query(TaskMember).filter(TaskMember.task_id == task_id).all()
    member_ids = [tm.user_id for tm in task_members]
    
    # 상위 업무 제목 조회
    parent_task_title = None
    if task.parent_task_id:
        parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
        parent_task_title = parent_task.title if parent_task else None
    
    return TaskResponse(
        **task.__dict__,
        assignee_name=task.assignee.name if task.assignee else None,
        parent_task_title=parent_task_title,
        member_ids=member_ids
    )


# 3) Task 삭제 엔드포인트
@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # 권한 검증: Task의 담당자만 삭제 가능
    if task.assignee_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="해당 Task의 담당자만 삭제할 수 있습니다"
        )
    
    # Task 삭제 전에 관련 정보 저장 (WebSocket 이벤트용)
    task_info = {
        "task_id": task.task_id,
        "project_id": task.project_id,
        "title": task.title
    }
    
    # Task 삭제 (관련 TaskMember도 CASCADE로 삭제됨)
    db.delete(task)
    db.commit()
    
    
    return None  # 204 No Content


# 상위업무만 조회하는 엔드포인트
@router.get("/parent-tasks", response_model=List[TaskResponse])
def read_parent_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    """프로젝트의 상위업무(is_parent_task=True)만 조회"""
    tasks = (
        db.query(TaskModel)
          .filter(TaskModel.project_id == project_id)
          .filter(TaskModel.is_parent_task == True)
          .all()
    )
    
    result = []
    for task in tasks:
        # task_members 조회
        task_members = db.query(TaskMember).filter(TaskMember.task_id == task.task_id).all()
        member_ids = [tm.user_id for tm in task_members]
        
        # 상위 업무 제목 조회
        parent_task_title = None
        if task.parent_task_id:
            parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
            parent_task_title = parent_task.title if parent_task else None
        
        result.append(TaskResponse(
            **task.__dict__,
            assignee_name=task.assignee.name if task.assignee else None,
            parent_task_title=parent_task_title,
            member_ids=member_ids
        ))
    
    return result


# 4) Task 상태 변경 전용 엔드포인트
@router.patch(
    "/tasks/{task_id}/status",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK
)
async def update_task_status(
    task_id: int,
    status_payload: dict,  # {"status": "complete"} 형태
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # 권한 검증: Task의 담당자만 상태 변경 가능
    if task.assignee_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="해당 Task의 담당자만 상태를 변경할 수 있습니다"
        )

    new_status = status_payload.get("status")
    if not new_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status is required")
    
    # 유효한 상태 값 검증
    valid_statuses = ["todo", "In progress", "complete"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    # 상태가 실제로 변경된 경우에만 업데이트
    if task.status != new_status:
        task.status = new_status
        db.commit()
        db.refresh(task)
        
    
    return task

