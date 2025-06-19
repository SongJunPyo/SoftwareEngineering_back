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
from backend.models.tag import Tag, TaskTag
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
    # 1) 담당자 필수 검증
    if task_in.assignee_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="담당자를 지정해주세요."
        )

    # 2) 프로젝트 유효성 검증
    project = db.query(Project).filter_by(
        project_id=task_in.project_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="프로젝트를 찾을 수 없습니다."
        )

    # 3) 현재 사용자가 프로젝트 멤버인지 검증 및 뷰어 권한 체크
    current_user_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task_in.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    if not current_user_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 업무를 생성할 수 있습니다."
        )
    
    # 뷰어 권한 체크 - 뷰어는 업무 생성 불가
    if current_user_member.role == 'viewer':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="뷰어는 업무를 생성할 수 없습니다."
        )

    # 4) 담당자가 프로젝트 멤버인지 검증
    assignee_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task_in.project_id,
        ProjectMember.user_id == task_in.assignee_id
    ).first()
    if not assignee_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="담당자가 해당 프로젝트의 멤버가 아닙니다."
        )

    # 5) 날짜 유효성 검증
    if task_in.start_date > task_in.due_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="시작일은 마감일보다 늦을 수 없습니다."
        )

    # 6) 상위 업무 유효성 검증
    if task_in.parent_task_id is not None:
        parent = db.query(TaskModel).filter_by(
            task_id=task_in.parent_task_id
        ).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="상위 업무를 찾을 수 없습니다."
            )
        
        # 상위 업무가 같은 프로젝트에 속하는지 검증
        if parent.project_id != task_in.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="상위 업무는 같은 프로젝트 내에서만 선택할 수 있습니다."
            )

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

    # 7) 태그 유효성 검증
    if task_in.tag_names:
        for tag_name in task_in.tag_names:
            existing_tag = db.query(Tag).filter(
                Tag.project_id == task_in.project_id,
                Tag.tag_name == tag_name
            ).first()
            if not existing_tag:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"태그 '{tag_name}'이 해당 프로젝트에 존재하지 않습니다."
                )

    # 8) tasks 테이블에 새 업무 저장 (assignee_id는 프론트에서 받은 값 사용)
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

    # 9) task_members 테이블에 매핑 추가 (담당자가 필수이므로 항상 추가)
    mapping = TaskMember(
        task_id     = task.task_id,
        user_id     = task_in.assignee_id,
    )
    db.add(mapping)
    
    # 10) 태그 할당
    if task_in.tag_names:
        for tag_name in task_in.tag_names:
            task_tag = TaskTag(
                task_id=task.task_id,
                tag_name=tag_name
            )
            db.add(task_tag)
    
    db.commit()
    
    
    # 11) 생성된 Task 객체를 TaskResponse 형태로 반환 (assignee_name 포함)
    # task_members 조회
    task_members = db.query(TaskMember).filter(TaskMember.task_id == task.task_id).all()
    member_ids = [tm.user_id for tm in task_members]
    
    # 태그 조회
    task_tags = db.query(TaskTag).filter(TaskTag.task_id == task.task_id).all()
    tag_names = [tt.tag_name for tt in task_tags]
    
    # 상위 업무 제목 조회
    parent_task_title = None
    if task.parent_task_id:
        parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
        parent_task_title = parent_task.title if parent_task else None
    
    return TaskResponse(
        **task.__dict__,
        assignee_name=task.assignee.name if task.assignee else None,
        parent_task_title=parent_task_title,
        member_ids=member_ids,
        tag_names=tag_names
    )

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
        
        # 태그 조회
        task_tags = db.query(TaskTag).filter(TaskTag.task_id == task.task_id).all()
        tag_names = [tt.tag_name for tt in task_tags]
        
        # 상위 업무 제목 조회
        parent_task_title = None
        if task.parent_task_id:
            parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
            parent_task_title = parent_task.title if parent_task else None
        
        result.append(TaskResponse(
            **task.__dict__,
            assignee_name=task.assignee.name if task.assignee else None,
            parent_task_title=parent_task_title,
            member_ids=member_ids,
            tag_names=tag_names
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업무를 찾을 수 없습니다.")

    # task_members 조회
    task_members = db.query(TaskMember).filter(TaskMember.task_id == task_id).all()
    member_ids = [tm.user_id for tm in task_members]

    # 태그 조회
    task_tags = db.query(TaskTag).filter(TaskTag.task_id == task_id).all()
    tag_names = [tt.tag_name for tt in task_tags]

    # 상위 업무 제목 조회
    parent_task_title = None
    if task.parent_task_id:
        parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
        parent_task_title = parent_task.title if parent_task else None

    return TaskResponse(
        **task.__dict__,
        assignee_name=task.assignee.name if task.assignee else None,
        parent_task_title=parent_task_title,
        member_ids=member_ids,
        tag_names=tag_names
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업무를 찾을 수 없습니다.")

    # 권한 검증: Task의 담당자 또는 프로젝트 멤버만 수정 가능
    project_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if task.assignee_id != current_user.user_id and not project_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="해당 업무의 담당자 또는 프로젝트 멤버만 수정할 수 있습니다."
        )
    
    # 뷰어 권한 체크 - 뷰어는 업무 수정 불가
    if project_member and project_member.role == 'viewer':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="뷰어는 업무를 수정할 수 없습니다."
        )
    
    # 담당자 변경 시 새 담당자가 프로젝트 멤버인지 검증
    if task_update.assignee_id is not None and task_update.assignee_id != task.assignee_id:
        new_assignee_member = db.query(ProjectMember).filter(
            ProjectMember.project_id == task.project_id,
            ProjectMember.user_id == task_update.assignee_id
        ).first()
        if not new_assignee_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="새 담당자가 해당 프로젝트의 멤버가 아닙니다."
            )
    
    # 날짜 유효성 검증
    start_date = task_update.start_date if task_update.start_date else task.start_date
    due_date = task_update.due_date if task_update.due_date else task.due_date
    
    # 문자열을 date 객체로 변환하여 비교
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date[:10], '%Y-%m-%d').date()
    elif isinstance(start_date, datetime):
        start_date = start_date.date()
        
    if isinstance(due_date, str):
        due_date = datetime.strptime(due_date[:10], '%Y-%m-%d').date()
    elif isinstance(due_date, datetime):
        due_date = due_date.date()
    
    if start_date > due_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="시작일은 마감일보다 늦을 수 없습니다."
        )
    
    # 상위 업무 변경 시 검증
    if task_update.parent_task_id is not None and task_update.parent_task_id != task.parent_task_id:
        # 자기 자신을 상위 업무로 설정하는 것 방지
        if task_update.parent_task_id == task.task_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="자기 자신을 상위 업무로 설정할 수 없습니다."
            )
        
        # 상위 업무 존재 여부 검증
        parent_task = db.query(TaskModel).filter(TaskModel.task_id == task_update.parent_task_id).first()
        if not parent_task:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="상위 업무를 찾을 수 없습니다."
            )
        
        # 상위 업무가 같은 프로젝트에 속하는지 검증
        if parent_task.project_id != task.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="상위 업무는 같은 프로젝트 내에서만 선택할 수 있습니다."
            )
        
        # 순환 참조 방지 (현재 업무가 새로운 상위 업무의 조상인지 확인)
        def check_circular_reference(current_task_id, target_parent_id):
            current = db.query(TaskModel).filter(TaskModel.task_id == target_parent_id).first()
            while current and current.parent_task_id:
                if current.parent_task_id == current_task_id:
                    return True
                current = db.query(TaskModel).filter(TaskModel.task_id == current.parent_task_id).first()
            return False
        
        if check_circular_reference(task.task_id, task_update.parent_task_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="상위 업무 설정으로 인해 순환 참조가 발생합니다."
            )
    
    updated = False
    
    # 업데이트 가능한 필드들 처리
    update_data = task_update.dict(exclude_unset=True, exclude={'member_ids', 'tag_names'})
    
    for field, new_value in update_data.items():
        if field in ['start_date', 'due_date'] and new_value:
            # 날짜 필드 처리
            if isinstance(new_value, str):
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
    
    # 태그 업데이트 처리
    if task_update.tag_names is not None:
        # 태그 유효성 검증
        for tag_name in task_update.tag_names:
            existing_tag = db.query(Tag).filter(
                Tag.project_id == task.project_id,
                Tag.tag_name == tag_name
            ).first()
            if not existing_tag:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"태그 '{tag_name}'이 해당 프로젝트에 존재하지 않습니다."
                )
        
        # 기존 task_tags 삭제
        db.query(TaskTag).filter(TaskTag.task_id == task_id).delete()
        
        # 새로운 task_tags 추가
        for tag_name in task_update.tag_names:
            task_tag = TaskTag(task_id=task_id, tag_name=tag_name)
            db.add(task_tag)
        
        updated = True
    
    if updated:
        # updated_at은 onupdate로 자동 설정되지만 명시적으로 설정
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
    
    # 응답에 member_ids와 parent_task_title 포함
    task_members = db.query(TaskMember).filter(TaskMember.task_id == task_id).all()
    member_ids = [tm.user_id for tm in task_members]
    
    # 태그 조회
    task_tags = db.query(TaskTag).filter(TaskTag.task_id == task_id).all()
    tag_names = [tt.tag_name for tt in task_tags]
    
    # 상위 업무 제목 조회
    parent_task_title = None
    if task.parent_task_id:
        parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
        parent_task_title = parent_task.title if parent_task else None
    
    return TaskResponse(
        **task.__dict__,
        assignee_name=task.assignee.name if task.assignee else None,
        parent_task_title=parent_task_title,
        member_ids=member_ids,
        tag_names=tag_names
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업무를 찾을 수 없습니다.")

    # 권한 검증: Task의 담당자만 삭제 가능
    if task.assignee_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="해당 업무의 담당자만 삭제할 수 있습니다."
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
        
        # 태그 조회
        task_tags = db.query(TaskTag).filter(TaskTag.task_id == task.task_id).all()
        tag_names = [tt.tag_name for tt in task_tags]
        
        # 상위 업무 제목 조회
        parent_task_title = None
        if task.parent_task_id:
            parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
            parent_task_title = parent_task.title if parent_task else None
        
        result.append(TaskResponse(
            **task.__dict__,
            assignee_name=task.assignee.name if task.assignee else None,
            parent_task_title=parent_task_title,
            member_ids=member_ids,
            tag_names=tag_names
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업무를 찾을 수 없습니다.")

    # 권한 검증: Task의 담당자만 상태 변경 가능
    if task.assignee_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="해당 업무의 담당자만 상태를 변경할 수 있습니다."
        )
    
    # 뷰어 권한 체크 - 뷰어는 업무 상태 변경 불가
    assignee_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if assignee_member and assignee_member.role == 'viewer':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="뷰어는 업무 상태를 변경할 수 없습니다."
        )

    new_status = status_payload.get("status")
    if not new_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="상태 값이 필요합니다.")
    
    # 유효한 상태 값 검증
    valid_statuses = ["todo", "In progress", "complete"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"올바르지 않은 상태입니다. 다음 중 하나여야 합니다: {', '.join(valid_statuses)}"
        )
    
    # 상태가 실제로 변경된 경우에만 업데이트
    if task.status != new_status:
        task.status = new_status
        db.commit()
        db.refresh(task)
        
    
    return task

