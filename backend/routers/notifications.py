from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from backend.database.base import get_db
from backend.models.logs_notification import Notification
from backend.models.user import User
from backend.middleware.auth import verify_token
from backend.websocket.events import event_emitter

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


async def create_notification(
    db: Session,
    user_id: int,
    type: str,
    message: str,
    channel: str = "general",
    related_id: int = None,
    title: str = None,
    emit_realtime: bool = True,
    project_id: int = None
):
    """알림을 생성하고 실시간 WebSocket 이벤트를 발행합니다."""
    print(f"🔔 알림 생성 시작 - 사용자: {user_id}, 타입: {type}, 메시지: {message}")
    
    notification = Notification(
        user_id=user_id,
        type=type,
        message=message,
        channel=channel,
        is_read=False,
        related_id=related_id
    )
    db.add(notification)
    db.flush()  # notification_id를 얻기 위해 flush
    
    print(f"💾 알림 DB 저장 완료 - ID: {notification.notification_id}")
    
    # 실시간 WebSocket 이벤트 발행
    if emit_realtime:
        try:
            # 알림 타입에 따라 적절한 WebSocket 이벤트 발행
            if type in ["task_assigned", "task_updated", "task_completed", "task_deadline", "task_priority_changed", "task_status_changed", "task_due_date_changed", "deadline_approaching", "task_overdue", "deadline_1day", "deadline_3days", "deadline_7days"]:
                # Task 관련 알림은 TASK_ASSIGNED 타입으로 발행
                from backend.websocket.message_types import MessageType, create_task_message, TaskEventData
                from backend.websocket.connection_manager import connection_manager
                
                task_data = TaskEventData(
                    task_id=related_id,
                    project_id=project_id or 0,  # 전달받은 project_id 사용
                    title=message,
                    assignee_id=user_id,
                    due_date=None  # 필요시 추가
                )
                
                message_obj = create_task_message(MessageType.TASK_ASSIGNED, task_data, f"user:{user_id}", user_id)
                await connection_manager.send_personal_message(message_obj.to_dict(), user_id)
                
            elif type in ["comment_created", "comment_mention"]:
                # 댓글 관련 알림은 COMMENT_MENTION 또는 COMMENT_CREATED 타입으로 발행
                from backend.websocket.message_types import MessageType, create_comment_message, CommentEventData
                from backend.websocket.connection_manager import connection_manager
                
                message_type = MessageType.COMMENT_MENTION if type == "comment_mention" else MessageType.COMMENT_CREATED
                
                comment_data = CommentEventData(
                    comment_id=0,  # 임시값, 필요시 파라미터로 받아올 수 있음
                    task_id=related_id,
                    project_id=project_id or 0,  # 전달받은 project_id 사용
                    content=message,
                    author_id=0,  # 임시값
                    author_name="",  # 임시값
                    mentions=[]
                )
                
                message_obj = create_comment_message(message_type, comment_data, f"user:{user_id}", user_id)
                await connection_manager.send_personal_message(message_obj.to_dict(), user_id)
                
            else:
                # 기타 알림은 일반 NOTIFICATION_NEW 타입으로 발행
                await event_emitter.emit_notification(
                    notification_id=notification.notification_id,
                    recipient_id=user_id,
                    title=title or get_notification_title(type),
                    message=message,
                    notification_type=type,
                    related_id=related_id
                )
        except Exception as e:
            print(f"WebSocket 알림 발행 실패: {e}")
    
    return notification


def get_notification_title(notification_type: str) -> str:
    """알림 타입에 따른 제목 반환"""
    title_map = {
        "task_assigned": "새로운 작업이 할당되었습니다",
        "task_updated": "작업이 업데이트되었습니다",
        "task_completed": "작업이 완료되었습니다",
        "task_deadline": "작업 마감일이 임박했습니다",
        "task_priority_changed": "작업 우선순위가 변경되었습니다",
        "task_status_changed": "작업 상태가 변경되었습니다",
        "task_due_date_changed": "작업 마감일이 변경되었습니다",
        "comment_created": "새로운 댓글이 작성되었습니다",
        "comment_mention": "댓글에서 멘션되었습니다",
        "project_invited": "프로젝트에 초대되었습니다",
        "project_member_added": "프로젝트 멤버로 추가되었습니다",
        "project_updated": "프로젝트가 업데이트되었습니다",
        "project_deleted": "프로젝트가 삭제되었습니다",
        "project_member_role_changed": "멤버 권한이 변경되었습니다",
        "invitation_accepted": "프로젝트 초대가 수락되었습니다",
        "invitation_declined": "프로젝트 초대가 거절되었습니다",
        "workspace_created": "새로운 워크스페이스가 생성되었습니다",
        "workspace_updated": "워크스페이스가 업데이트되었습니다",
        "workspace_deleted": "워크스페이스가 삭제되었습니다",
        "workspace_shared": "워크스페이스가 공유되었습니다",
        "deadline_approaching": "마감일이 임박했습니다",
        "task_overdue": "작업이 연체되었습니다",
        "deadline_1day": "마감일 1일 전 알림",
        "deadline_3days": "마감일 3일 전 알림",
        "deadline_7days": "마감일 7일 전 알림",
        "welcome_message": "Planora에 오신 것을 환영합니다",
        "account_verification": "계정 인증이 완료되었습니다",
        "system": "시스템 알림"
    }
    return title_map.get(notification_type, "새로운 알림")


async def create_task_notification(
    db: Session,
    user_id: int,
    task_id: int,
    task_title: str,
    notification_type: str,
    actor_name: str = None,
    project_id: int = None
):
    """Task 관련 알림 생성"""
    type_messages = {
        "task_assigned": f"새로운 작업 '{task_title}'이 할당되었습니다.",
        "task_updated": f"작업 '{task_title}'이 업데이트되었습니다.",
        "task_completed": f"작업 '{task_title}'이 완료되었습니다.",
        "task_deadline": f"작업 '{task_title}'의 마감일이 임박했습니다.",
        "task_priority_changed": f"작업 '{task_title}'의 우선순위가 변경되었습니다.",
        "task_status_changed": f"작업 '{task_title}'의 상태가 변경되었습니다.",
        "task_due_date_changed": f"작업 '{task_title}'의 마감일이 변경되었습니다.",
        "deadline_approaching": f"작업 '{task_title}'의 마감일이 임박했습니다.",
        "task_overdue": f"작업 '{task_title}'이 연체되었습니다.",
        "deadline_1day": f"작업 '{task_title}'의 마감일이 1일 남았습니다.",
        "deadline_3days": f"작업 '{task_title}'의 마감일이 3일 남았습니다.",
        "deadline_7days": f"작업 '{task_title}'의 마감일이 1주일 남았습니다."
    }
    
    if actor_name:
        type_messages.update({
            "task_assigned": f"{actor_name}님이 작업 '{task_title}'을 할당했습니다.",
            "task_updated": f"{actor_name}님이 작업 '{task_title}'을 업데이트했습니다.",
            "task_completed": f"{actor_name}님이 작업 '{task_title}'을 완료했습니다.",
            "task_priority_changed": f"{actor_name}님이 작업 '{task_title}'의 우선순위를 변경했습니다.",
            "task_status_changed": f"{actor_name}님이 작업 '{task_title}'의 상태를 변경했습니다.",
            "task_due_date_changed": f"{actor_name}님이 작업 '{task_title}'의 마감일을 변경했습니다."
        })
    
    message = type_messages.get(notification_type, f"작업 '{task_title}'에 대한 업데이트가 있습니다.")
    
    return await create_notification(
        db=db,
        user_id=user_id,
        type=notification_type,
        message=message,
        channel="task",
        related_id=task_id,
        title=get_notification_title(notification_type),
        project_id=project_id
    )


async def create_comment_notification(
    db: Session,
    user_id: int,
    task_id: int,
    task_title: str,
    comment_author: str,
    is_mention: bool = False,
    project_id: int = None
):
    """댓글 관련 알림 생성"""
    if is_mention:
        notification_type = "comment_mention"
        message = f"{comment_author}님이 '{task_title}' 작업 댓글에서 회원님을 멘션했습니다."
    else:
        notification_type = "comment_created"
        message = f"{comment_author}님이 '{task_title}' 작업에 댓글을 작성했습니다."
    
    return await create_notification(
        db=db,
        user_id=user_id,
        type=notification_type,
        message=message,
        channel="comment",
        related_id=task_id,
        title=get_notification_title(notification_type),
        project_id=project_id  # project_id 전달
    )


async def create_project_notification(
    db: Session,
    user_id: int,
    project_id: int,
    project_name: str,
    notification_type: str,
    actor_name: str = None
):
    """프로젝트 관련 알림 생성"""
    type_messages = {
        "project_invited": f"'{project_name}' 프로젝트에 초대되었습니다.",
        "project_member_added": f"'{project_name}' 프로젝트 멤버로 추가되었습니다.",
        "project_updated": f"'{project_name}' 프로젝트가 업데이트되었습니다.",
        "project_deleted": f"'{project_name}' 프로젝트가 삭제되었습니다.",
        "project_member_role_changed": f"'{project_name}' 프로젝트에서 권한이 변경되었습니다."
    }
    
    if actor_name:
        type_messages.update({
            "project_invited": f"{actor_name}님이 '{project_name}' 프로젝트에 초대했습니다.",
            "project_member_added": f"{actor_name}님이 회원님을 '{project_name}' 프로젝트에 추가했습니다.",
            "project_updated": f"{actor_name}님이 '{project_name}' 프로젝트를 업데이트했습니다.",
            "project_deleted": f"{actor_name}님이 '{project_name}' 프로젝트를 삭제했습니다.",
            "project_member_role_changed": f"{actor_name}님이 '{project_name}' 프로젝트에서 회원님의 권한을 변경했습니다."
        })
    
    message = type_messages.get(notification_type, f"'{project_name}' 프로젝트에 대한 업데이트가 있습니다.")
    
    return await create_notification(
        db=db,
        user_id=user_id,
        type=notification_type,
        message=message,
        channel="project",
        related_id=project_id,
        title=get_notification_title(notification_type)
    )


@router.get("/")
async def get_notifications(
    page: int = 1,
    per_page: int = 10,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # 페이지네이션 파라미터 검증
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:  # 최대 100개로 제한
        per_page = 10
    
    # 페이지네이션 계산
    offset = (page - 1) * per_page
    
    notifications = db.query(Notification)\
        .filter(Notification.user_id == current_user.user_id)\
        .order_by(Notification.created_at.desc())\
        .offset(offset)\
        .limit(per_page)\
        .all()
    
    total = db.query(Notification)\
        .filter(Notification.user_id == current_user.user_id)\
        .count()

    return {
        "items": [n.to_dict() for n in notifications],
        "total": total
    }

@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    notification = db.query(Notification)\
        .filter(Notification.notification_id == notification_id)\
        .first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    
    # 실시간 읽음 처리 이벤트 발행
    try:
        from backend.websocket.message_types import MessageType, create_notification_message, NotificationEventData
        
        notification_data = NotificationEventData(
            notification_id=notification.notification_id,
            recipient_id=notification.user_id,
            title="알림 읽음 처리",
            message="알림이 읽음 처리되었습니다.",
            notification_type="notification_read",
            related_id=notification.related_id,
            is_read=True
        )
        
        message = create_notification_message(
            MessageType.NOTIFICATION_READ,
            notification_data,
            current_user.user_id
        )
        
        from backend.websocket.connection_manager import connection_manager
        await connection_manager.send_personal_message(message.to_dict(), current_user.user_id)
        
    except Exception as e:
        print(f"WebSocket 읽음 처리 이벤트 발행 실패: {e}")
    
    return {"result": "success", "notification": notification.to_dict()}


@router.patch("/mark-all-read")
async def mark_all_as_read(
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """모든 읽지 않은 알림을 읽음 처리"""
    unread_notifications = db.query(Notification)\
        .filter(Notification.user_id == current_user.user_id)\
        .filter(Notification.is_read == False)\
        .all()
    
    if not unread_notifications:
        return {"result": "success", "updated_count": 0}
    
    # 모든 알림을 읽음 처리
    for notification in unread_notifications:
        notification.is_read = True
    
    db.commit()
    
    # 실시간 이벤트 발행
    try:
        from backend.websocket.connection_manager import connection_manager
        
        message = {
            "type": "notifications_all_read",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "user_id": current_user.user_id,
                "updated_count": len(unread_notifications),
                "notification_ids": [n.notification_id for n in unread_notifications]
            }
        }
        
        await connection_manager.send_personal_message(message, current_user.user_id)
        
    except Exception as e:
        print(f"WebSocket 모든 알림 읽음 처리 이벤트 발행 실패: {e}")
    
    return {
        "result": "success", 
        "updated_count": len(unread_notifications),
        "notifications": [n.to_dict() for n in unread_notifications]
    }


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """읽지 않은 알림 개수 조회"""
    count = db.query(Notification)\
        .filter(Notification.user_id == current_user.user_id)\
        .filter(Notification.is_read == False)\
        .count()
    
    return {"unread_count": count}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """알림 삭제"""
    notification = db.query(Notification)\
        .filter(Notification.notification_id == notification_id)\
        .first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    db.delete(notification)
    db.commit()
    
    # 실시간 삭제 이벤트 발행
    try:
        from backend.websocket.connection_manager import connection_manager
        
        message = {
            "type": "notification_deleted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "notification_id": notification_id,
                "user_id": current_user.user_id
            }
        }
        
        await connection_manager.send_personal_message(message, current_user.user_id)
        
    except Exception as e:
        print(f"WebSocket 알림 삭제 이벤트 발행 실패: {e}")
    
    return {"result": "success"}