from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from backend.database.base import get_db
from backend.middleware.auth import verify_token
from backend.models.task import Task as TaskModel
from backend.models.task import TaskMember
from backend.models.project import Project
from backend.schemas.Task import TaskCreateRequest, TaskResponse
from backend.models.logs_notification import ActivityLog

router = APIRouter(prefix="/api/v1")

@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED
)
def create_task(
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

    # # 3) tasks 테이블에 새 업무 저장 (assignee_id는 프론트에서 받은 값 사용)
    # task = TaskModel(
    #     title           = task_in.title,
    #     project_id      = task_in.project_id,
    #     parent_task_id  = task_in.parent_task_id,
    #     start_date      = task_in.start_date,
    #     due_date        = task_in.due_date,
    #     priority        = task_in.priority,
    #     assignee_id     = task_in.assignee_id,
    # )
    # db.add(task)
    # db.commit()
    # db.refresh(task)
        # === status 자동 결정 ===
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
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 4) ActivityLog에 기록 추가
    log = ActivityLog(
        user_id=current_user.user_id,
        entity_type="task",
        entity_id=task.task_id,
        action="create",
        project_id=task.project_id
    )
    db.add(log)
    db.commit()

    # 5) task_members 테이블에 매핑 추가 (project_id, user_id, assigned_at)
    if task_in.assignee_id is not None:
        mapping = TaskMember(
            task_id     = task.task_id,
            user_id     = task_in.assignee_id,
        )
        db.add(mapping)
    db.commit()
    # 6) 생성된 Task 객체를 반환 (TaskOut 직렬화)
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
    # assignee 관계를 통해 User.name 이 이미 로드되어 있으므로:
    return [
      TaskResponse(
        **task.__dict__,              # TaskCreate 필드 + task_id, created_at 등
        assignee_name=task.assignee.name if task.assignee else None
      )
      for task in tasks
    ]

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

    # assignee_name이 TaskResponse 스키마에 포함돼 있다면, Task 모델에 relationship이 있어야 함
    return task

# 2) Task description 업데이트 엔드포인트
@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK
)
def update_task_description(
    task_id: int,
    payload: dict,  # {"description": "새로운 설명"} 형태를 가정
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # 권한 체크가 필요하다면 여기에 추가 (예: 같은 프로젝트 멤버인지 등)
    new_description = payload.get("description")
    task.description = new_description
    db.commit()
    db.refresh(task)
    return task




# # backend/routers/tasks.py
# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.orm import Session
# from typing import List
# from datetime import datetime, timezone

# from backend.database.base import get_db
# from backend.middleware.auth import verify_token
# from backend.models.task import Task as TaskModel
# from backend.models.task import TaskMember
# from backend.models.project import Project
# from backend.schemas.Task import TaskCreate, TaskOut



# @router.post(
#     "/tasks/",
#     response_model=TaskOut,
#     status_code=status.HTTP_201_CREATED
# )
# def create_task(
#     task_in: TaskCreate,
#     db: Session = Depends(get_db),
#     current_user = Depends(verify_token),
# ):
#     # 1) 프로젝트 유효성 검증
#     project = db.query(Project).filter_by(
#         project_id=task_in.project_id
#     ).first()
#     if not project:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

#     # 2) (선택) 상위 업무 유효성 검증
#     if task_in.parent_task_id is not None:
#         parent = db.query(TaskModel).filter_by(
#             task_id=task_in.parent_task_id
#         ).first()
#         if not parent:
#             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent task not found")

#     # 3) tasks 테이블에 새 업무 저장 (assignee_id는 프론트에서 받은 값 사용)
#     task = TaskModel(
#         name            = task_in.name,
#         project_id      = task_in.project_id,
#         parent_task_id  = task_in.parent_task_id,
#         start_date      = task_in.start_date,
#         due_date        = task_in.due_date,
#         priority        = task_in.priority,
#         assignee_id     = task_in.assignee_id,
#     )
#     db.add(task)
#     db.commit()
#     db.refresh(task)

#     # 4) task_members 테이블에 매핑 추가 (project_id, user_id, assigned_at)
#     mapping = TaskMember(
#         task_id     = task.task_id,
#         project_id  = task.project_id,
#         user_id     = task_in.assignee_id,
#         assigned_at = datetime.now(timezone.utc)
#     )
#     db.add(mapping)
#     db.commit()

#     # 5) 생성된 Task 객체를 반환 (TaskOut 직렬화)
#     return task

# @router.get("/tasks/", response_model=List[TaskOut])
# def read_tasks(
#     project_id: int,
#     db: Session = Depends(get_db),
#     current_user = Depends(verify_token),
# ):
#     tasks = (
#         db.query(TaskModel)
#           .filter(TaskModel.project_id == project_id)
#           .all()
#     )
#     # assignee 관계를 통해 User.name 이 이미 로드되어 있으므로:
#     return [
#       TaskOut(
#         **task.__dict__,              # TaskCreate 필드 + task_id, created_at 등
#         assignee_name=task.assignee.name if task.assignee else None
#       )
#       for task in tasks
#     ]
