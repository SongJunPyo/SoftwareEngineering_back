from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import asyncio
from pydantic import BaseModel

from backend.database.base import get_db
from backend.middleware.auth import verify_token
from backend.models.task import Task as TaskModel
from backend.models.task import TaskMember
from backend.models.project import Project, ProjectMember
from backend.models.tag import Tag, TaskTag
from backend.schemas.Task import TaskCreateRequest, TaskUpdateRequest, TaskResponse
from backend.models.logs_notification import ActivityLog
from backend.models.user import User
from backend.routers.notifications import create_task_notification
from backend.websocket.events import event_emitter
from backend.utils.activity_logger import log_task_activity

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

    # 프론트엔드에서 status가 전송된 경우 해당 값 사용, 없으면 자동 계산
    if hasattr(task_in, 'status') and task_in.status:
        # 프론트엔드 상태값을 백엔드 형식으로 변환
        frontend_to_backend_status = {
            "todo": "todo",
            "in_progress": "in_progress", 
            "pending": "pending",
            "complete": "complete"
        }
        status_value = frontend_to_backend_status.get(task_in.status, task_in.status)
        
        # "할 일" 상태 디버깅
        if task_in.status == 'todo' or status_value == 'todo':
            print(f"🔍 백엔드 - '할 일' 상태 처리: {task_in.status} -> {status_value}")
    else:
        # 자동 계산 로직
        if now < start_date:
            status_value = "todo"
        elif start_date <= now <= due_date:
            status_value = "in_progress"
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

    # 8) tasks 테이블에 새 업무 저장
    task = TaskModel(
        title           = task_in.title,
        project_id      = task_in.project_id,
        parent_task_id  = task_in.parent_task_id,
        start_date      = task_in.start_date,
        due_date        = task_in.due_date,
        priority        = task_in.priority,
        assignee_id     = task_in.assignee_id,
        status          = status_value,
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
    
    # 11) ActivityLog에 기록 추가
    log_task_activity(
        db=db,
        user=current_user,
        task_id=task.task_id,
        action="create",
        project_id=task.project_id,
        task_title=task.title
    )
    
    # 12) 모든 DB 변경사항을 한 번에 커밋
    db.commit()
    
    # 13) 실시간 WebSocket 이벤트 발행 (Task 생성 + 할당 알림 통합)
    try:
        print(f"🚀 Task 생성 이벤트 발행 시작 - Task ID: {task.task_id}, 담당자: {task_in.assignee_id}")
        
        # 담당자 정보 조회
        assignee = db.query(User).filter(User.user_id == task_in.assignee_id).first()
        assignee_name = assignee.name if assignee else None
        
        print(f"👤 담당자 정보: {assignee_name} (ID: {task_in.assignee_id})")
        
        # Task 생성 이벤트 발행 (프로젝트 멤버들에게)
        print(f"📤 Task 생성 이벤트 발행 중...")
        await event_emitter.emit_task_created(
            task_id=task.task_id,
            project_id=task.project_id,
            title=task.title,
            created_by=current_user.user_id,
            created_by_name=current_user.name,
            assignee_id=task_in.assignee_id,
            assignee_name=assignee_name,
            description=task.description,
            due_date=task.due_date.strftime('%Y-%m-%dT00:00:00') if task.due_date else None,
            priority=task.priority,
            tags=task_in.tag_names or [],
            status=status_value  # 상태 값 추가
        )
        print(f"✅ Task 생성 이벤트 발행 완료")
        
        # 담당자에게 할당 알림 발행 (본인이 아닌 경우)
        if task_in.assignee_id and task_in.assignee_id != current_user.user_id:
            print(f"🔔 Task 할당 알림 발행 중 - 수신자: {task_in.assignee_id}")
            await create_task_notification(
                db=db,
                user_id=task_in.assignee_id,
                task_id=task.task_id,
                task_title=task.title,
                notification_type="task_assigned",
                actor_name=current_user.name,
                project_id=task.project_id
            )
            db.commit()  # 알림 저장을 위한 추가 커밋
            print(f"✅ Task 할당 알림 발행 완료")
        else:
            print(f"⏭️ 본인에게 할당되어 알림 생략")
            
    except Exception as e:
        print(f"❌ Task 생성 WebSocket 이벤트 발행 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 14) 생성된 Task 객체를 TaskResponse 형태로 반환
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

    # 권한 검증: 소유자/관리자는 모든 업무 수정 가능, 멤버는 본인 담당 업무만 수정 가능
    project_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if not project_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 업무를 수정할 수 있습니다."
        )
    
    # 뷰어는 수정 불가
    if project_member.role == 'viewer':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="뷰어는 업무를 수정할 수 없습니다."
        )
    
    # 멤버는 본인 담당 업무만 수정 가능, 소유자/관리자는 모든 업무 수정 가능
    if project_member.role == 'member' and task.assignee_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="멤버는 본인이 담당한 업무만 수정할 수 있습니다."
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
    
    # 변경 사항 추적을 위한 변수들
    priority_changed = False
    status_changed = False
    due_date_changed = False
    assignee_changed = False
    old_priority = task.priority
    old_status = task.status
    old_due_date = task.due_date
    old_assignee_id = task.assignee_id
    
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
        elif field == 'status' and new_value:
            # 상태 필드 처리 - 프론트엔드 형식을 백엔드 형식으로 변환
            valid_frontend_statuses = ["todo", "in_progress", "pending", "complete"]
            if new_value not in valid_frontend_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"올바르지 않은 상태입니다. 다음 중 하나여야 합니다: {', '.join(valid_frontend_statuses)}"
                )
            # 모든 상태값을 그대로 사용 (더 이상 변환하지 않음)
            # 프론트엔드와 백엔드가 동일한 상태값을 사용하도록 통일
        
        # 기존 값과 다른 경우에만 업데이트
        if getattr(task, field) != new_value:
            # 특정 필드 변경 추적
            if field == 'priority':
                priority_changed = True
            elif field == 'status':
                status_changed = True
            elif field == 'due_date':
                due_date_changed = True
            elif field == 'assignee_id':
                assignee_changed = True
            
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
        
        # WebSocket 이벤트 발행 (Task 업데이트)
        try:
            # 담당자 정보 조회
            assignee = db.query(User).filter(User.user_id == task.assignee_id).first() if task.assignee_id else None
            assignee_name = assignee.name if assignee else None
            
            await event_emitter.emit_task_updated(
                task_id=task.task_id,
                project_id=task.project_id,
                title=task.title,
                updated_by=current_user.user_id,
                status=task.status,
                assignee_id=task.assignee_id,
                assignee_name=assignee_name,
                description=task.description,
                due_date=task.due_date.strftime('%Y-%m-%dT00:00:00') if task.due_date else None,
                priority=task.priority,
                tags=tag_names
            )
        except Exception as e:
            print(f"Task 업데이트 WebSocket 이벤트 발행 실패: {e}")
        
        # Activity Log 작성
        try:
            # 전반적인 업데이트 로그
            log_task_activity(
                db=db,
                user=current_user,
                task_id=task.task_id,
                action="update",
                project_id=task.project_id,
                task_title=task.title
            )
            
            # 특정 변경사항에 대한 상세 로그
            if status_changed:
                log_task_activity(
                    db=db,
                    user=current_user,
                    task_id=task.task_id,
                    action="status_change",
                    project_id=task.project_id,
                    task_title=task.title,
                    old_status=old_status,
                    new_status=task.status
                )
            
            if assignee_changed:
                # 새 담당자 이름 조회
                new_assignee = db.query(User).filter(User.user_id == task.assignee_id).first()
                assignee_name = new_assignee.name if new_assignee else None
                
                log_task_activity(
                    db=db,
                    user=current_user,
                    task_id=task.task_id,
                    action="assign",
                    project_id=task.project_id,
                    task_title=task.title,
                    assignee_name=assignee_name
                )
            
        except Exception as e:
            print(f"Task 업데이트 로그 작성 실패: {e}")
        
        # 특정 필드 변경에 대한 알림 생성
        try:
            if priority_changed and task.assignee_id and task.assignee_id != current_user.user_id:
                await create_task_notification(
                    db=db,
                    user_id=task.assignee_id,
                    task_id=task.task_id,
                    task_title=task.title,
                    notification_type="task_priority_changed",
                    actor_name=current_user.name,
                    project_id=task.project_id
                )
            
            if status_changed and task.assignee_id and task.assignee_id != current_user.user_id:
                await create_task_notification(
                    db=db,
                    user_id=task.assignee_id,
                    task_id=task.task_id,
                    task_title=task.title,
                    notification_type="task_status_changed",
                    actor_name=current_user.name,
                    project_id=task.project_id
                )
            
            if due_date_changed and task.assignee_id and task.assignee_id != current_user.user_id:
                await create_task_notification(
                    db=db,
                    user_id=task.assignee_id,
                    task_id=task.task_id,
                    task_title=task.title,
                    notification_type="task_due_date_changed",
                    actor_name=current_user.name,
                    project_id=task.project_id
                )
            
            # 변경 사항이 있으면 추가 커밋
            if priority_changed or status_changed or due_date_changed:
                db.commit()
                
        except Exception as e:
            print(f"Task 변경 알림 생성 실패: {e}")
    
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

    # 권한 검증: 소유자/관리자는 모든 업무 삭제 가능, 멤버는 본인 담당 업무만 삭제 가능
    project_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == task.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if not project_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 프로젝트의 멤버만 업무를 삭제할 수 있습니다."
        )
    
    # 뷰어는 삭제 불가
    if project_member.role == 'viewer':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="뷰어는 업무를 삭제할 수 없습니다."
        )
    
    # 멤버는 본인 담당 업무만 삭제 가능, 소유자/관리자는 모든 업무 삭제 가능
    if project_member.role == 'member' and task.assignee_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="멤버는 본인이 담당한 업무만 삭제할 수 있습니다."
        )
    
    # 하위 업무 존재 여부 확인 - 하위 업무가 있는 상위 업무는 삭제 불가
    child_tasks = db.query(TaskModel).filter(TaskModel.parent_task_id == task_id).all()
    if child_tasks:
        child_task_titles = [child.title for child in child_tasks]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"상위 업무는 하위 업무가 있을 때 삭제할 수 없습니다. 먼저 {len(child_tasks)}개의 하위 업무를 삭제하거나 다른 상위 업무로 이동해주세요.\n\n하위 업무: {', '.join(child_task_titles)}"
        )
    
    # Task 삭제 전에 관련 정보 저장 (WebSocket 이벤트용)
    task_info = {
        "task_id": task.task_id,
        "project_id": task.project_id,
        "title": task.title
    }
    
    # Activity Log 작성 (삭제 전에)
    try:
        log_task_activity(
            db=db,
            user=current_user,
            task_id=task.task_id,
            action="delete",
            project_id=task.project_id,
            task_title=task.title
        )
        db.commit()  # 로그를 먼저 커밋
    except Exception as e:
        print(f"Task 삭제 로그 작성 실패: {e}")
    
    # Task 삭제 (관련 TaskMember도 CASCADE로 삭제됨)
    db.delete(task)
    db.commit()
    
    # WebSocket 이벤트 발행 (Task 삭제)
    try:
        await event_emitter.emit_task_deleted(
            task_id=task_info["task_id"],
            project_id=task_info["project_id"],
            title=task_info["title"],
            deleted_by=current_user.user_id
        )
    except Exception as e:
        print(f"Task 삭제 WebSocket 이벤트 발행 실패: {e}")
    
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


# Task 상태 변경 요청 모델
class TaskStatusUpdateRequest(BaseModel):
    status: str

# 4) Task 상태 변경 전용 엔드포인트
@router.patch(
    "/tasks/{task_id}/status",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK
)
async def update_task_status(
    task_id: int,
    status_payload: TaskStatusUpdateRequest,  # Pydantic 모델 사용
    db: Session = Depends(get_db),
    current_user = Depends(verify_token),
):
    # 🔍 COMPREHENSIVE DEBUG LOGGING - START
    print(f"\n{'='*80}")
    print(f"🔍 TASK STATUS UPDATE DEBUG LOG")
    print(f"{'='*80}")
    
    # 1. 요청 정보 로깅
    print(f"📥 REQUEST INFO:")
    print(f"   Task ID: {task_id} (type: {type(task_id)})")
    print(f"   Raw payload: {status_payload}")
    print(f"   Payload dict: {status_payload.dict()}")
    print(f"   Status value: '{status_payload.status}' (type: {type(status_payload.status)})")
    print(f"   Status length: {len(status_payload.status) if status_payload.status else 'None'}")
    
    # 2. 사용자 정보 로깅
    print(f"👤 USER INFO:")
    print(f"   User ID: {current_user.user_id}")
    print(f"   User name: {current_user.name}")
    print(f"   User email: {getattr(current_user, 'email', 'N/A')}")
    
    # 3. Task 조회 및 검증
    print(f"🔍 TASK LOOKUP:")
    try:
        task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
        if not task:
            print(f"❌ Task not found with ID: {task_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업무를 찾을 수 없습니다.")
        else:
            print(f"✅ Task found:")
            print(f"   Task ID: {task.task_id}")
            print(f"   Title: {task.title}")
            print(f"   Current status: '{task.status}'")
            print(f"   Project ID: {task.project_id}")
            print(f"   Assignee ID: {task.assignee_id}")
    except Exception as e:
        print(f"💥 ERROR during task lookup: {e}")
        print(f"   Exception type: {type(e)}")
        raise

    # 4. 권한 검증 로깅
    print(f"🔐 PERMISSION CHECK:")
    try:
        project_member = db.query(ProjectMember).filter(
            ProjectMember.project_id == task.project_id,
            ProjectMember.user_id == current_user.user_id
        ).first()
        
        if not project_member:
            print(f"❌ User is not a project member")
            print(f"   Project ID: {task.project_id}")
            print(f"   User ID: {current_user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 프로젝트의 멤버만 업무 상태를 변경할 수 있습니다."
            )
        else:
            print(f"✅ User is project member:")
            print(f"   Role: {project_member.role}")
            print(f"   Project ID: {project_member.project_id}")
            print(f"   User ID: {project_member.user_id}")
    except HTTPException as he:
        print(f"🚫 Permission denied: {he.detail}")
        raise
    except Exception as e:
        print(f"💥 ERROR during permission check: {e}")
        print(f"   Exception type: {type(e)}")
        raise
    
    # 5. 뷰어 권한 체크
    if project_member.role == 'viewer':
        print(f"❌ User is viewer - cannot modify tasks")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="뷰어는 업무 상태를 변경할 수 없습니다."
        )
    
    # 6. 멤버 권한 체크 (본인 담당 업무만)
    if project_member.role == 'member' and task.assignee_id != current_user.user_id:
        print(f"❌ Member can only modify own tasks")
        print(f"   Task assignee: {task.assignee_id}")
        print(f"   Current user: {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="멤버는 본인이 담당한 업무의 상태만 변경할 수 있습니다."
        )
    
    print(f"✅ Permission check passed")

    # 7. 상태 값 검증
    print(f"✅ STATUS VALIDATION:")
    new_status = status_payload.status
    print(f"   New status: '{new_status}'")
    print(f"   Status type: {type(new_status)}")
    print(f"   Status repr: {repr(new_status)}")
    
    if not new_status:
        print(f"❌ Empty status value")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="상태 값이 필요합니다.")
    
    # 유효한 상태 값 검증 (프론트엔드 형식)
    valid_frontend_statuses = ["todo", "in_progress", "pending", "complete"]
    print(f"   Valid statuses: {valid_frontend_statuses}")
    
    if new_status not in valid_frontend_statuses:
        print(f"❌ Invalid status value: '{new_status}'")
        print(f"   Status in valid list: {new_status in valid_frontend_statuses}")
        print(f"   Checking each valid status:")
        for vs in valid_frontend_statuses:
            print(f"     '{vs}' == '{new_status}': {vs == new_status}")
            print(f"     '{vs}' repr: {repr(vs)}")
            print(f"     '{new_status}' repr: {repr(new_status)}")
        
        error_msg = f"올바르지 않은 상태입니다. 다음 중 하나여야 합니다: {', '.join(valid_frontend_statuses)}"
        print(f"   Error message: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=error_msg
        )
    
    # 8. 상태값 그대로 사용 (변환하지 않음)
    print(f"   Status validation passed - using status as-is: '{new_status}'")
    
    print(f"   Final status: '{new_status}'")
    
    # 9. 상태 업데이트
    print(f"🔄 STATUS UPDATE:")
    print(f"   Current status: '{task.status}'")
    print(f"   New status: '{new_status}'")
    print(f"   Status changed: {task.status != new_status}")
    
    if task.status != new_status:
        old_status = task.status
        print(f"   Updating status from '{old_status}' to '{new_status}'")
        
        try:
            task.status = new_status
            db.commit()
            db.refresh(task)
            print(f"✅ Status updated successfully")
            print(f"   Task status after update: '{task.status}'")
        except Exception as e:
            print(f"💥 ERROR during database update: {e}")
            print(f"   Exception type: {type(e)}")
            db.rollback()
            raise
        
        # WebSocket 이벤트 발행 (Task 상태 변경)
        try:
            print(f"📡 Emitting WebSocket event...")
            await event_emitter.emit_task_status_changed(
                task_id=task.task_id,
                project_id=task.project_id,
                title=task.title,
                old_status=old_status,
                new_status=new_status,
                updated_by=current_user.user_id,
                assignee_id=task.assignee_id
            )
            print(f"✅ WebSocket event emitted successfully")
        except Exception as e:
            print(f"⚠️ WebSocket event emission failed: {e}")
            print(f"   Exception type: {type(e)}")
            # Don't raise - WebSocket failure shouldn't break the API
        
        # Activity Log 작성
        try:
            print(f"📝 Writing activity log...")
            log_task_activity(
                db=db,
                user=current_user,
                task_id=task.task_id,
                action="status_change",
                project_id=task.project_id,
                task_title=task.title,
                old_status=old_status,
                new_status=new_status
            )
            db.commit()
            print(f"✅ Activity log written successfully")
        except Exception as e:
            print(f"⚠️ Activity log writing failed: {e}")
            print(f"   Exception type: {type(e)}")
            # Don't raise - Log failure shouldn't break the API
    else:
        print(f"⏭️ Status unchanged - skipping update")
    
    # 10. 응답 준비
    print(f"📤 PREPARING RESPONSE:")
    try:
        # TaskResponse 형태로 반환
        task_members = db.query(TaskMember).filter(TaskMember.task_id == task_id).all()
        member_ids = [tm.user_id for tm in task_members]
        print(f"   Task members: {member_ids}")
        
        # 태그 조회
        task_tags = db.query(TaskTag).filter(TaskTag.task_id == task_id).all()
        tag_names = [tt.tag_name for tt in task_tags]
        print(f"   Task tags: {tag_names}")
        
        # 상위 업무 제목 조회
        parent_task_title = None
        if task.parent_task_id:
            parent_task = db.query(TaskModel).filter(TaskModel.task_id == task.parent_task_id).first()
            parent_task_title = parent_task.title if parent_task else None
        print(f"   Parent task title: {parent_task_title}")
        
        response = TaskResponse(
            **task.__dict__,
            assignee_name=task.assignee.name if task.assignee else None,
            parent_task_title=parent_task_title,
            member_ids=member_ids,
            tag_names=tag_names
        )
        print(f"✅ Response prepared successfully")
        print(f"   Response status: '{response.status}'")
        print(f"{'='*80}")
        print(f"🎉 TASK STATUS UPDATE COMPLETED SUCCESSFULLY")
        print(f"{'='*80}\n")
        
        return response
        
    except Exception as e:
        print(f"💥 ERROR during response preparation: {e}")
        print(f"   Exception type: {type(e)}")
        print(f"   Task dict: {task.__dict__}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}")
        print(f"💥 TASK STATUS UPDATE FAILED")
        print(f"{'='*80}\n")
        raise

