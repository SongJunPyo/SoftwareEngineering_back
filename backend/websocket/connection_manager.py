from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket
import json
import logging
from datetime import datetime
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    WebSocket 연결 관리자
    - 사용자별 연결 추적
    - 룸(방) 기반 그룹 통신
    - 메시지 브로드캐스트
    - 연결 상태 관리
    """
    
    def __init__(self):
        # 활성 연결: {user_id: [websocket_connections]}
        self.active_connections: Dict[int, List[WebSocket]] = defaultdict(list)
        
        # 룸별 사용자: {room_id: {user_id1, user_id2, ...}}
        self.rooms: Dict[str, Set[int]] = defaultdict(set)
        
        # 사용자별 참여 룸: {user_id: {room_id1, room_id2, ...}}
        self.user_rooms: Dict[int, Set[str]] = defaultdict(set)
        
        # WebSocket별 사용자 매핑: {websocket: user_id}
        self.connection_user_map: Dict[WebSocket, int] = {}
        
        # 연결 시간 추적
        self.connection_times: Dict[WebSocket, datetime] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """사용자 연결 추가"""
        try:
            await websocket.accept()
            
            self.active_connections[user_id].append(websocket)
            self.connection_user_map[websocket] = user_id
            self.connection_times[websocket] = datetime.utcnow()
            
            # 개인 알림 룸에 자동 참여
            personal_room = f"user:{user_id}"
            await self.join_room(user_id, personal_room)
            
            logger.info(f"User {user_id} connected. Total connections: {len(self.active_connections[user_id])}")
            
            # 연결 확인 메시지 전송
            await self.send_personal_message({
                "type": "connection_established",
                "message": "WebSocket 연결이 성공적으로 설정되었습니다.",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id
            }, user_id)
            
        except Exception as e:
            logger.error(f"Error connecting user {user_id}: {e}")
            raise
    
    async def disconnect(self, websocket: WebSocket):
        """연결 해제 및 정리"""
        try:
            user_id = self.connection_user_map.get(websocket)
            if user_id is None:
                return
            
            # 연결 목록에서 제거
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            # 사용자의 모든 연결이 끊어진 경우 룸에서 제거
            if not self.active_connections[user_id]:
                await self._leave_all_rooms(user_id)
                del self.active_connections[user_id]
            
            # 매핑 정리
            del self.connection_user_map[websocket]
            if websocket in self.connection_times:
                del self.connection_times[websocket]
            
            logger.info(f"User {user_id} disconnected. Remaining connections: {len(self.active_connections.get(user_id, []))}")
            
        except Exception as e:
            logger.error(f"Error disconnecting websocket: {e}")
    
    async def send_personal_message(self, message: dict, user_id: int):
        """특정 사용자에게 메시지 전송"""
        if user_id not in self.active_connections:
            logger.warning(f"User {user_id} not connected")
            return False
        
        message_str = json.dumps(message, ensure_ascii=False)
        disconnected_connections = []
        
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send message to user {user_id}: {e}")
                disconnected_connections.append(connection)
        
        # 끊어진 연결 정리
        for connection in disconnected_connections:
            await self.disconnect(connection)
        
        return len(disconnected_connections) == 0
    
    async def broadcast_to_room(self, room_id: str, message: dict, exclude_user: Optional[int] = None):
        """룸의 모든 사용자에게 메시지 브로드캐스트"""
        if room_id not in self.rooms:
            logger.warning(f"Room {room_id} not found")
            return
        
        message["room_id"] = room_id
        sent_count = 0
        failed_users = []
        
        for user_id in self.rooms[room_id]:
            if exclude_user and user_id == exclude_user:
                continue
            
            success = await self.send_personal_message(message, user_id)
            if success:
                sent_count += 1
            else:
                failed_users.append(user_id)
        
        if failed_users:
            logger.warning(f"Failed to send message to users: {failed_users} in room {room_id}")
        
        logger.info(f"Broadcast to room {room_id}: {sent_count} users reached")
        return sent_count
    
    async def join_room(self, user_id: int, room_id: str):
        """사용자를 룸에 추가"""
        self.rooms[room_id].add(user_id)
        self.user_rooms[user_id].add(room_id)
        
        logger.info(f"User {user_id} joined room {room_id}. Room size: {len(self.rooms[room_id])}")
        
        # 룸 참여 확인 메시지
        await self.send_personal_message({
            "type": "room_joined",
            "room_id": room_id,
            "message": f"룸 {room_id}에 참여했습니다.",
            "timestamp": datetime.utcnow().isoformat()
        }, user_id)
    
    async def leave_room(self, user_id: int, room_id: str):
        """사용자를 룸에서 제거"""
        if room_id in self.rooms:
            self.rooms[room_id].discard(user_id)
            if not self.rooms[room_id]:  # 빈 룸 정리
                del self.rooms[room_id]
        
        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(room_id)
            if not self.user_rooms[user_id]:
                del self.user_rooms[user_id]
        
        logger.info(f"User {user_id} left room {room_id}")
        
        # 룸 나감 확인 메시지
        await self.send_personal_message({
            "type": "room_left",
            "room_id": room_id,
            "message": f"룸 {room_id}에서 나갔습니다.",
            "timestamp": datetime.utcnow().isoformat()
        }, user_id)
    
    async def _leave_all_rooms(self, user_id: int):
        """사용자를 모든 룸에서 제거"""
        if user_id not in self.user_rooms:
            return
        
        rooms_to_leave = list(self.user_rooms[user_id])
        for room_id in rooms_to_leave:
            await self.leave_room(user_id, room_id)
    
    def get_room_members(self, room_id: str) -> List[int]:
        """룸의 멤버 목록 반환"""
        return list(self.rooms.get(room_id, set()))
    
    def get_user_rooms(self, user_id: int) -> List[str]:
        """사용자가 참여한 룸 목록 반환"""
        return list(self.user_rooms.get(user_id, set()))
    
    def is_user_online(self, user_id: int) -> bool:
        """사용자 온라인 상태 확인"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0
    
    def get_online_users(self) -> List[int]:
        """온라인 사용자 목록 반환"""
        return [user_id for user_id, connections in self.active_connections.items() if connections]
    
    def get_connection_stats(self) -> dict:
        """연결 통계 정보"""
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        return {
            "total_users": len(self.active_connections),
            "total_connections": total_connections,
            "total_rooms": len(self.rooms),
            "online_users": self.get_online_users()
        }


# 전역 연결 관리자 인스턴스
connection_manager = ConnectionManager()