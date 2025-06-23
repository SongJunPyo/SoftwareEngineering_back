from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime


class MessageType(str, Enum):
    """WebSocket 메시지 타입 정의"""
    
    # 시스템 메시지
    CONNECTION_ESTABLISHED = "connection_established"
    ROOM_JOINED = "room_joined"
    ROOM_LEFT = "room_left"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    
    # 알림 관련
    NOTIFICATION_NEW = "notification_new"
    NOTIFICATION_READ = "notification_read"
    NOTIFICATION_DELETED = "notification_deleted"
    
    # Task 관련
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_DELETED = "task_deleted"
    TASK_STATUS_CHANGED = "task_status_changed"
    TASK_ASSIGNED = "task_assigned"
    TASK_UNASSIGNED = "task_unassigned"
    TASK_COMMENT_ADDED = "task_comment_added"
    
    # Comment 관련
    COMMENT_CREATED = "comment_created"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"
    COMMENT_MENTION = "comment_mention"
    
    # Project 관련
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_DELETED = "project_deleted"
    PROJECT_MEMBER_ADDED = "project_member_added"
    PROJECT_MEMBER_REMOVED = "project_member_removed"
    PROJECT_MEMBER_ROLE_CHANGED = "project_member_role_changed"
    PROJECT_INVITATION_SENT = "project_invitation_sent"
    
    # Workspace 관련
    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_UPDATED = "workspace_updated"
    WORKSPACE_DELETED = "workspace_deleted"
    WORKSPACE_ORDER_CHANGED = "workspace_order_changed"
    
    # 사용자 상태
    USER_ONLINE = "user_online"
    USER_OFFLINE = "user_offline"
    USER_TYPING = "user_typing"
    USER_STOP_TYPING = "user_stop_typing"


class RoomType(str, Enum):
    """룸 타입 정의"""
    USER = "user"           # 개인 알림 룸: user:{user_id}
    PROJECT = "project"     # 프로젝트 룸: project:{project_id}
    WORKSPACE = "workspace" # 워크스페이스 룸: workspace:{workspace_id}
    TASK = "task"          # 특정 태스크 룸: task:{task_id}


class WebSocketMessage(BaseModel):
    """기본 WebSocket 메시지 구조"""
    type: MessageType
    timestamp: datetime = None
    room_id: Optional[str] = None
    user_id: Optional[int] = None
    data: Dict[str, Any] = {}
    
    def __init__(self, **data):
        if data.get('timestamp') is None:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)
    
    def to_dict(self) -> dict:
        """메시지를 딕셔너리로 변환"""
        result = {
            "type": self.type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "data": self.data
        }
        
        if self.room_id:
            result["room_id"] = self.room_id
        if self.user_id:
            result["user_id"] = self.user_id
            
        return result


# 특정 메시지 타입별 데이터 구조

class TaskEventData(BaseModel):
    """Task 이벤트 데이터"""
    task_id: int
    project_id: int
    title: str
    status: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = []


class CommentEventData(BaseModel):
    """Comment 이벤트 데이터"""
    comment_id: int
    task_id: int
    project_id: int
    content: str
    author_id: int
    author_name: str
    mentions: Optional[List[int]] = []  # 멘션된 사용자 ID 목록
    parent_comment_id: Optional[int] = None


class ProjectEventData(BaseModel):
    """Project 이벤트 데이터"""
    project_id: int
    workspace_id: int
    name: str
    description: Optional[str] = None
    owner_id: int
    owner_name: str
    member_id: Optional[int] = None  # 멤버 관련 이벤트시
    member_name: Optional[str] = None
    role: Optional[str] = None


class NotificationEventData(BaseModel):
    """Notification 이벤트 데이터"""
    notification_id: int
    recipient_id: int
    title: str
    message: str
    notification_type: str
    related_id: Optional[int] = None  # 관련된 엔티티 ID (task_id, project_id 등)
    is_read: bool = False


class UserStatusEventData(BaseModel):
    """사용자 상태 이벤트 데이터"""
    user_id: int
    username: str
    status: str  # online, offline, typing, etc.
    project_id: Optional[int] = None  # 타이핑 상태의 경우 어느 프로젝트에서인지


# 메시지 생성 헬퍼 함수들

def create_task_message(
    message_type: MessageType,
    task_data: TaskEventData,
    room_id: str,
    user_id: Optional[int] = None
) -> WebSocketMessage:
    """Task 관련 메시지 생성"""
    return WebSocketMessage(
        type=message_type,
        room_id=room_id,
        user_id=user_id,
        data=task_data.dict()
    )


def create_comment_message(
    message_type: MessageType,
    comment_data: CommentEventData,
    room_id: str,
    user_id: Optional[int] = None
) -> WebSocketMessage:
    """Comment 관련 메시지 생성"""
    return WebSocketMessage(
        type=message_type,
        room_id=room_id,
        user_id=user_id,
        data=comment_data.dict()
    )


def create_project_message(
    message_type: MessageType,
    project_data: ProjectEventData,
    room_id: str,
    user_id: Optional[int] = None
) -> WebSocketMessage:
    """Project 관련 메시지 생성"""
    return WebSocketMessage(
        type=message_type,
        room_id=room_id,
        user_id=user_id,
        data=project_data.dict()
    )


def create_notification_message(
    message_type: MessageType,
    notification_data: NotificationEventData,
    user_id: int
) -> WebSocketMessage:
    """Notification 관련 메시지 생성"""
    return WebSocketMessage(
        type=message_type,
        room_id=f"user:{user_id}",
        user_id=user_id,
        data=notification_data.dict()
    )


def create_user_status_message(
    message_type: MessageType,
    status_data: UserStatusEventData,
    room_id: str
) -> WebSocketMessage:
    """사용자 상태 메시지 생성"""
    return WebSocketMessage(
        type=message_type,
        room_id=room_id,
        user_id=status_data.user_id,
        data=status_data.dict()
    )


def create_error_message(
    error_message: str,
    user_id: int,
    error_code: Optional[str] = None
) -> WebSocketMessage:
    """에러 메시지 생성"""
    return WebSocketMessage(
        type=MessageType.ERROR,
        room_id=f"user:{user_id}",
        user_id=user_id,
        data={
            "message": error_message,
            "error_code": error_code
        }
    )


# 룸 ID 생성 헬퍼 함수들

def get_user_room_id(user_id: int) -> str:
    """사용자 개인 룸 ID 생성"""
    return f"{RoomType.USER}:{user_id}"


def get_project_room_id(project_id: int) -> str:
    """프로젝트 룸 ID 생성"""
    return f"{RoomType.PROJECT}:{project_id}"


def get_workspace_room_id(workspace_id: int) -> str:
    """워크스페이스 룸 ID 생성"""
    return f"{RoomType.WORKSPACE}:{workspace_id}"


def get_task_room_id(task_id: int) -> str:
    """태스크 룸 ID 생성"""
    return f"{RoomType.TASK}:{task_id}"