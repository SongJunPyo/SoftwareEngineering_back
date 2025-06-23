from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional
from backend.models.logs_notification import ActivityLog
from backend.models.user import User
from backend.models.project import Project


def log_activity(
    db: Session,
    user: User,
    entity_type: str,
    entity_id: int,
    action: str,
    project_id: Optional[int] = None,
    details: Optional[str] = None
):
    """
    활동 로그를 데이터베이스에 기록합니다.
    
    Args:
        db: 데이터베이스 세션
        user: 작업을 수행한 사용자
        entity_type: 엔티티 타입 (task, comment, project, tag, file 등)
        entity_id: 엔티티 ID
        action: 수행한 액션 (create, update, delete, assign, status_change 등)
        project_id: 프로젝트 ID (선택사항)
        details: 상세 내용 (선택사항)
    """
    try:
        # 프로젝트 이름 가져오기
        project_name = None
        if project_id:
            project = db.query(Project).filter(Project.project_id == project_id).first()
            if project:
                project_name = project.title

        # ActivityLog 생성
        activity_log = ActivityLog(
            user_id=user.user_id,
            user_name=user.name,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            project_id=project_id,
            project_name=project_name,
            details=details,
            timestamp=datetime.now(timezone.utc)
        )
        
        db.add(activity_log)
        db.commit()
        
    except Exception as e:
        print(f"ActivityLog 생성 실패: {e}")
        db.rollback()


def log_task_activity(
    db: Session,
    user: User,
    task_id: int,
    action: str,
    project_id: int,
    task_title: Optional[str] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    assignee_name: Optional[str] = None
):
    """Task 관련 활동 로그를 기록합니다."""
    details = None
    
    if action == "create" and task_title:
        details = f"업무 '{task_title}' 생성"
    elif action == "update" and task_title:
        details = f"업무 '{task_title}' 수정"
    elif action == "delete" and task_title:
        details = f"업무 '{task_title}' 삭제"
    elif action == "status_change" and old_status and new_status:
        details = f"상태 변경: {old_status} → {new_status}"
    elif action == "assign" and assignee_name:
        details = f"{assignee_name}에게 할당"
    
    log_activity(
        db=db,
        user=user,
        entity_type="task",
        entity_id=task_id,
        action=action,
        project_id=project_id,
        details=details
    )


def log_comment_activity(
    db: Session,
    user: User,
    comment_id: int,
    action: str,
    project_id: int,
    task_id: Optional[int] = None,
    comment_content: Optional[str] = None
):
    """Comment 관련 활동 로그를 기록합니다."""
    details = None
    
    if comment_content:
        # 댓글 내용이 너무 길면 잘라서 저장
        max_length = 100
        if len(comment_content) > max_length:
            details = comment_content[:max_length] + "..."
        else:
            details = comment_content
    
    log_activity(
        db=db,
        user=user,
        entity_type="comment",
        entity_id=comment_id,
        action=action,
        project_id=project_id,
        details=details
    )


def log_project_activity(
    db: Session,
    user: User,
    project_id: int,
    action: str,
    project_name: Optional[str] = None
):
    """Project 관련 활동 로그를 기록합니다."""
    details = None
    
    if action == "create" and project_name:
        details = f"프로젝트 '{project_name}' 생성"
    elif action == "update" and project_name:
        details = f"프로젝트 '{project_name}' 수정"
    elif action == "delete" and project_name:
        details = f"프로젝트 '{project_name}' 삭제"
    
    log_activity(
        db=db,
        user=user,
        entity_type="project",
        entity_id=project_id,
        action=action,
        project_id=project_id,
        details=details
    )


def log_tag_activity(
    db: Session,
    user: User,
    tag_name: str,
    action: str,
    project_id: int,
    task_id: Optional[int] = None
):
    """Tag 관련 활동 로그를 기록합니다."""
    details = f"태그 '{tag_name}'"
    
    if action == "create":
        details += " 할당"
    elif action == "delete":
        details += " 제거"
    
    # tag_name을 entity_id 대신 사용하기 위해 hash 사용
    entity_id = hash(tag_name) % (10**9)  # 간단한 해시 ID 생성
    
    log_activity(
        db=db,
        user=user,
        entity_type="tag",
        entity_id=entity_id,
        action=action,
        project_id=project_id,
        details=details
    )