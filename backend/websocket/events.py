from typing import List, Optional, Dict, Any
import logging
from sqlalchemy.orm import Session

from .connection_manager import connection_manager
from .message_types import (
    MessageType, TaskEventData, CommentEventData, ProjectEventData,
    NotificationEventData, UserStatusEventData,
    create_task_message, create_comment_message, create_project_message,
    create_notification_message, create_user_status_message,
    get_user_room_id, get_project_room_id, get_workspace_room_id, get_task_room_id
)

logger = logging.getLogger(__name__)


class WebSocketEventEmitter:
    """WebSocket 이벤트 발행 클래스"""
    
    def __init__(self):
        self.manager = connection_manager
    
    # Task 관련 이벤트들
    
    async def emit_task_created(
        self,
        task_id: int,
        project_id: int,
        title: str,
        created_by: int,
        created_by_name: str,
        assignee_id: Optional[int] = None,
        assignee_name: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        """Task 생성 이벤트 발행"""
        task_data = TaskEventData(
            task_id=task_id,
            project_id=project_id,
            title=title,
            created_by=created_by,
            created_by_name=created_by_name,
            assignee_id=assignee_id,
            assignee_name=assignee_name,
            description=description,
            due_date=due_date,
            priority=priority,
            tags=tags or []
        )
        
        project_room = get_project_room_id(project_id)
        message = create_task_message(MessageType.TASK_CREATED, task_data, project_room, created_by)
        
        await self.manager.broadcast_to_room(project_room, message.to_dict())
        
        # 할당된 사용자가 있으면 개인 알림도 전송
        if assignee_id and assignee_id != created_by:
            user_room = get_user_room_id(assignee_id)
            personal_message = create_task_message(MessageType.TASK_ASSIGNED, task_data, user_room, assignee_id)
            await self.manager.send_personal_message(personal_message.to_dict(), assignee_id)
    
    async def emit_task_updated(
        self,
        task_id: int,
        project_id: int,
        title: str,
        updated_by: int,
        status: Optional[str] = None,
        assignee_id: Optional[int] = None,
        assignee_name: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        """Task 업데이트 이벤트 발행"""
        task_data = TaskEventData(
            task_id=task_id,
            project_id=project_id,
            title=title,
            status=status,
            assignee_id=assignee_id,
            assignee_name=assignee_name,
            description=description,
            due_date=due_date,
            priority=priority,
            tags=tags or []
        )
        
        project_room = get_project_room_id(project_id)
        message = create_task_message(MessageType.TASK_UPDATED, task_data, project_room, updated_by)
        
        await self.manager.broadcast_to_room(project_room, message.to_dict())
    
    async def emit_task_status_changed(
        self,
        task_id: int,
        project_id: int,
        title: str,
        old_status: str,
        new_status: str,
        updated_by: int,
        assignee_id: Optional[int] = None
    ):
        """Task 상태 변경 이벤트 발행"""
        task_data = TaskEventData(
            task_id=task_id,
            project_id=project_id,
            title=title,
            status=new_status,
            assignee_id=assignee_id
        )
        
        # 상태 변경 정보 추가
        task_data_dict = task_data.dict()
        task_data_dict.update({
            "old_status": old_status,
            "new_status": new_status,
            "updated_by": updated_by
        })
        
        project_room = get_project_room_id(project_id)
        message = create_task_message(MessageType.TASK_STATUS_CHANGED, task_data, project_room, updated_by)
        message.data = task_data_dict
        
        await self.manager.broadcast_to_room(project_room, message.to_dict())
    
    async def emit_task_deleted(self, task_id: int, project_id: int, title: str, deleted_by: int):
        """Task 삭제 이벤트 발행"""
        task_data = TaskEventData(
            task_id=task_id,
            project_id=project_id,
            title=title
        )
        
        project_room = get_project_room_id(project_id)
        message = create_task_message(MessageType.TASK_DELETED, task_data, project_room, deleted_by)
        
        await self.manager.broadcast_to_room(project_room, message.to_dict())
    
    # Comment 관련 이벤트들
    
    async def emit_comment_created(
        self,
        comment_id: int,
        task_id: int,
        project_id: int,
        content: str,
        author_id: int,
        author_name: str,
        mentions: Optional[List[int]] = None,
        parent_comment_id: Optional[int] = None
    ):
        """댓글 생성 이벤트 발행"""
        comment_data = CommentEventData(
            comment_id=comment_id,
            task_id=task_id,
            project_id=project_id,
            content=content,
            author_id=author_id,
            author_name=author_name,
            mentions=mentions or [],
            parent_comment_id=parent_comment_id
        )
        
        # 프로젝트 룸에 브로드캐스트
        project_room = get_project_room_id(project_id)
        message = create_comment_message(MessageType.COMMENT_CREATED, comment_data, project_room, author_id)
        await self.manager.broadcast_to_room(project_room, message.to_dict())
        
        # 멘션된 사용자들에게 개별 알림
        if mentions:
            for mentioned_user_id in mentions:
                if mentioned_user_id != author_id:  # 자기 자신 제외
                    mention_message = create_comment_message(
                        MessageType.COMMENT_MENTION,
                        comment_data,
                        get_user_room_id(mentioned_user_id),
                        mentioned_user_id
                    )
                    await self.manager.send_personal_message(mention_message.to_dict(), mentioned_user_id)
    
    async def emit_comment_updated(
        self,
        comment_id: int,
        task_id: int,
        project_id: int,
        content: str,
        author_id: int,
        author_name: str
    ):
        """댓글 수정 이벤트 발행"""
        comment_data = CommentEventData(
            comment_id=comment_id,
            task_id=task_id,
            project_id=project_id,
            content=content,
            author_id=author_id,
            author_name=author_name
        )
        
        project_room = get_project_room_id(project_id)
        message = create_comment_message(MessageType.COMMENT_UPDATED, comment_data, project_room, author_id)
        await self.manager.broadcast_to_room(project_room, message.to_dict())
    
    async def emit_comment_deleted(
        self,
        comment_id: int,
        task_id: int,
        project_id: int,
        deleted_by: int
    ):
        """댓글 삭제 이벤트 발행"""
        comment_data = CommentEventData(
            comment_id=comment_id,
            task_id=task_id,
            project_id=project_id,
            content="",  # 삭제된 댓글이므로 내용 없음
            author_id=deleted_by,
            author_name=""
        )
        
        project_room = get_project_room_id(project_id)
        message = create_comment_message(MessageType.COMMENT_DELETED, comment_data, project_room, deleted_by)
        await self.manager.broadcast_to_room(project_room, message.to_dict())
    
    # Project 관련 이벤트들
    
    async def emit_project_member_added(
        self,
        project_id: int,
        workspace_id: int,
        project_name: str,
        member_id: int,
        member_name: str,
        role: str,
        added_by: int
    ):
        """프로젝트 멤버 추가 이벤트 발행"""
        project_data = ProjectEventData(
            project_id=project_id,
            workspace_id=workspace_id,
            name=project_name,
            owner_id=added_by,
            owner_name="",
            member_id=member_id,
            member_name=member_name,
            role=role
        )
        
        # 프로젝트 룸에 브로드캐스트
        project_room = get_project_room_id(project_id)
        message = create_project_message(MessageType.PROJECT_MEMBER_ADDED, project_data, project_room, added_by)
        await self.manager.broadcast_to_room(project_room, message.to_dict())
        
        # 새 멤버를 프로젝트 룸에 자동 참여시킴
        await self.manager.join_room(member_id, project_room)
        
        # 새 멤버에게 개인 알림
        user_room = get_user_room_id(member_id)
        personal_message = create_project_message(MessageType.PROJECT_MEMBER_ADDED, project_data, user_room, member_id)
        await self.manager.send_personal_message(personal_message.to_dict(), member_id)
    
    async def emit_project_member_removed(
        self,
        project_id: int,
        workspace_id: int,
        project_name: str,
        member_id: int,
        member_name: str,
        removed_by: int
    ):
        """프로젝트 멤버 제거 이벤트 발행"""
        project_data = ProjectEventData(
            project_id=project_id,
            workspace_id=workspace_id,
            name=project_name,
            owner_id=removed_by,
            owner_name="",
            member_id=member_id,
            member_name=member_name
        )
        
        # 프로젝트 룸에 브로드캐스트
        project_room = get_project_room_id(project_id)
        message = create_project_message(MessageType.PROJECT_MEMBER_REMOVED, project_data, project_room, removed_by)
        await self.manager.broadcast_to_room(project_room, message.to_dict())
        
        # 제거된 멤버를 프로젝트 룸에서 제거
        await self.manager.leave_room(member_id, project_room)
    
    # Notification 관련 이벤트들
    
    async def emit_notification(
        self,
        notification_id: int,
        recipient_id: int,
        title: str,
        message: str,
        notification_type: str,
        related_id: Optional[int] = None
    ):
        """알림 발행"""
        notification_data = NotificationEventData(
            notification_id=notification_id,
            recipient_id=recipient_id,
            title=title,
            message=message,
            notification_type=notification_type,
            related_id=related_id
        )
        
        message_obj = create_notification_message(MessageType.NOTIFICATION_NEW, notification_data, recipient_id)
        await self.manager.send_personal_message(message_obj.to_dict(), recipient_id)
    
    # 사용자 상태 이벤트들
    
    async def emit_user_online(self, user_id: int, username: str, project_ids: List[int]):
        """사용자 온라인 상태 이벤트 발행"""
        status_data = UserStatusEventData(
            user_id=user_id,
            username=username,
            status="online"
        )
        
        # 사용자가 속한 모든 프로젝트에 알림
        for project_id in project_ids:
            project_room = get_project_room_id(project_id)
            message = create_user_status_message(MessageType.USER_ONLINE, status_data, project_room)
            await self.manager.broadcast_to_room(project_room, message.to_dict(), exclude_user=user_id)
    
    async def emit_user_offline(self, user_id: int, username: str, project_ids: List[int]):
        """사용자 오프라인 상태 이벤트 발행"""
        status_data = UserStatusEventData(
            user_id=user_id,
            username=username,
            status="offline"
        )
        
        # 사용자가 속한 모든 프로젝트에 알림
        for project_id in project_ids:
            project_room = get_project_room_id(project_id)
            message = create_user_status_message(MessageType.USER_OFFLINE, status_data, project_room)
            await self.manager.broadcast_to_room(project_room, message.to_dict(), exclude_user=user_id)
    
    async def emit_user_typing(self, user_id: int, username: str, project_id: int):
        """사용자 타이핑 상태 이벤트 발행"""
        status_data = UserStatusEventData(
            user_id=user_id,
            username=username,
            status="typing",
            project_id=project_id
        )
        
        project_room = get_project_room_id(project_id)
        message = create_user_status_message(MessageType.USER_TYPING, status_data, project_room)
        await self.manager.broadcast_to_room(project_room, message.to_dict(), exclude_user=user_id)
    
    # 유틸리티 메서드들
    
    async def join_user_to_project_rooms(self, user_id: int, project_ids: List[int]):
        """사용자를 여러 프로젝트 룸에 참여시킴"""
        for project_id in project_ids:
            project_room = get_project_room_id(project_id)
            await self.manager.join_room(user_id, project_room)
    
    async def join_user_to_workspace_rooms(self, user_id: int, workspace_ids: List[int]):
        """사용자를 여러 워크스페이스 룸에 참여시킴"""
        for workspace_id in workspace_ids:
            workspace_room = get_workspace_room_id(workspace_id)
            await self.manager.join_room(user_id, workspace_room)


# 전역 이벤트 이미터 인스턴스
event_emitter = WebSocketEventEmitter()