from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import json
import logging
from typing import Optional, List
import asyncio
from datetime import datetime

from ..database.base import get_db
from ..models.user import User
from ..models.project import Project
from ..models.workspace import Workspace
from ..utils.jwt_utils import decode_token
from .connection_manager import connection_manager
from .events import event_emitter
from .message_types import MessageType, create_error_message, get_project_room_id, get_workspace_room_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


async def authenticate_websocket(token: str, db: Session) -> Optional[User]:
    """WebSocket 연결용 JWT 토큰 인증"""
    try:
        if not token:
            return None
        
        # Bearer 접두사 제거
        if token.startswith("Bearer "):
            token = token[7:]
        
        # JWT 토큰 디코딩
        payload = decode_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # 사용자 조회
        user = db.query(User).filter(User.user_id == int(user_id)).first()
        if not user:
            return None
        
        return user
        
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        return None


async def get_user_projects(user_id: int, db: Session) -> List[int]:
    """사용자가 속한 프로젝트 ID 목록 조회"""
    try:
        # 사용자가 멤버로 속한 프로젝트들 조회
        from ..models.project import ProjectMember
        
        project_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == user_id
        ).all()
        
        return [project_id[0] for project_id in project_ids]
        
    except Exception as e:
        logger.error(f"Error getting user projects: {e}")
        return []


async def get_user_workspaces(user_id: int, db: Session) -> List[int]:
    """사용자가 속한 워크스페이스 ID 목록 조회"""
    try:
        workspaces = db.query(Workspace.workspace_id).filter(
            Workspace.user_id == user_id
        ).all()
        
        return [workspace_id[0] for workspace_id in workspaces]
        
    except Exception as e:
        logger.error(f"Error getting user workspaces: {e}")
        return []


@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    WebSocket 연결 엔드포인트
    
    사용법:
    ws://localhost:8005/ws/connect?token=JWT_TOKEN
    """
    
    # 토큰 인증
    user = await authenticate_websocket(token, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
        return
    
    user_id = user.user_id
    username = user.name
    
    try:
        # WebSocket 연결 수락 및 연결 관리자에 등록
        await connection_manager.connect(websocket, user_id)
        
        # 사용자가 속한 프로젝트와 워크스페이스 룸에 참여
        user_projects = await get_user_projects(user_id, db)
        user_workspaces = await get_user_workspaces(user_id, db)
        
        await event_emitter.join_user_to_project_rooms(user_id, user_projects)
        await event_emitter.join_user_to_workspace_rooms(user_id, user_workspaces)
        
        # 다른 사용자들에게 온라인 상태 알림
        await event_emitter.emit_user_online(user_id, username, user_projects)
        
        logger.info(f"User {user_id} ({username}) connected to WebSocket")
        
        # 연결 유지 및 메시지 처리 루프
        while True:
            try:
                # 클라이언트로부터 메시지 수신 (타임아웃 30초)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # 메시지 처리
                await handle_client_message(websocket, user_id, message, db)
                
            except asyncio.TimeoutError:
                # 30초마다 heartbeat 전송
                await websocket.send_text(json.dumps({
                    "type": MessageType.HEARTBEAT,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "ping"
                }))
                
            except WebSocketDisconnect:
                logger.info(f"User {user_id} disconnected from WebSocket")
                break
                
            except Exception as e:
                logger.error(f"Error handling message from user {user_id}: {e}")
                error_message = create_error_message(
                    f"메시지 처리 중 오류가 발생했습니다: {str(e)}", 
                    user_id
                )
                await websocket.send_text(json.dumps(error_message.to_dict()))
    
    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from WebSocket")
    
    except Exception as e:
        logger.error(f"WebSocket connection error for user {user_id}: {e}")
    
    finally:
        # 연결 정리
        await connection_manager.disconnect(websocket)
        
        # 다른 사용자들에게 오프라인 상태 알림
        user_projects = await get_user_projects(user_id, db)
        await event_emitter.emit_user_offline(user_id, username, user_projects)


async def handle_client_message(websocket: WebSocket, user_id: int, message: str, db: Session):
    """클라이언트로부터 받은 메시지 처리"""
    try:
        data = json.loads(message)
        message_type = data.get("type")
        
        if message_type == "heartbeat":
            # Heartbeat 응답
            await websocket.send_text(json.dumps({
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "pong"
            }))
            
        elif message_type == "join_room":
            # 특정 룸 참여
            room_id = data.get("room_id")
            if room_id:
                await connection_manager.join_room(user_id, room_id)
                
        elif message_type == "leave_room":
            # 특정 룸 나가기
            room_id = data.get("room_id")
            if room_id:
                await connection_manager.leave_room(user_id, room_id)
                
        elif message_type == "typing":
            # 타이핑 상태 알림
            project_id = data.get("project_id")
            if project_id:
                username = db.query(User.name).filter(User.user_id == user_id).scalar()
                await event_emitter.emit_user_typing(user_id, username, project_id)
                
        elif message_type == "stop_typing":
            # 타이핑 중지 알림
            project_id = data.get("project_id")
            if project_id:
                username = db.query(User.name).filter(User.user_id == user_id).scalar()
                status_data = {
                    "user_id": user_id,
                    "username": username,
                    "status": "stop_typing",
                    "project_id": project_id
                }
                project_room = get_project_room_id(project_id)
                await connection_manager.broadcast_to_room(
                    project_room,
                    {
                        "type": MessageType.USER_STOP_TYPING,
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": status_data
                    },
                    exclude_user=user_id
                )
                
        elif message_type == "get_room_members":
            # 룸 멤버 목록 조회
            room_id = data.get("room_id")
            if room_id:
                members = connection_manager.get_room_members(room_id)
                await websocket.send_text(json.dumps({
                    "type": "room_members",
                    "room_id": room_id,
                    "members": members,
                    "timestamp": datetime.utcnow().isoformat()
                }))
                
        elif message_type == "get_connection_stats":
            # 연결 통계 조회 (관리자용)
            stats = connection_manager.get_connection_stats()
            await websocket.send_text(json.dumps({
                "type": "connection_stats",
                "data": stats,
                "timestamp": datetime.utcnow().isoformat()
            }))
            
        else:
            logger.warning(f"Unknown message type: {message_type} from user {user_id}")
            error_message = create_error_message(f"알 수 없는 메시지 타입: {message_type}", user_id)
            await websocket.send_text(json.dumps(error_message.to_dict()))
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from user {user_id}: {e}")
        error_message = create_error_message("올바르지 않은 JSON 형식입니다.", user_id)
        await websocket.send_text(json.dumps(error_message.to_dict()))
        
    except Exception as e:
        logger.error(f"Error handling client message from user {user_id}: {e}")
        error_message = create_error_message(f"메시지 처리 중 오류가 발생했습니다: {str(e)}", user_id)
        await websocket.send_text(json.dumps(error_message.to_dict()))


@router.get("/stats")
async def get_websocket_stats():
    """WebSocket 연결 통계 조회 (REST API)"""
    stats = connection_manager.get_connection_stats()
    return {
        "status": "success",
        "data": stats,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/online-users")
async def get_online_users():
    """온라인 사용자 목록 조회 (REST API)"""
    online_users = connection_manager.get_online_users()
    return {
        "status": "success",
        "online_users": online_users,
        "count": len(online_users),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/broadcast/{room_id}")
async def broadcast_message_to_room(
    room_id: str,
    message: dict,
    current_user: User = Depends(lambda: None)  # 추후 인증 미들웨어 적용
):
    """특정 룸에 메시지 브로드캐스트 (관리자용 REST API)"""
    try:
        message["timestamp"] = datetime.utcnow().isoformat()
        sent_count = await connection_manager.broadcast_to_room(room_id, message)
        
        return {
            "status": "success",
            "room_id": room_id,
            "sent_count": sent_count,
            "message": "메시지가 성공적으로 브로드캐스트되었습니다."
        }
        
    except Exception as e:
        logger.error(f"Error broadcasting message to room {room_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메시지 브로드캐스트 중 오류가 발생했습니다: {str(e)}"
        )