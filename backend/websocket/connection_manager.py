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
        print(f"🎯 개인 메시지 전송 시도 - 사용자: {user_id}")
        print(f"📝 메시지 타입: {message.get('type', 'unknown')}")
        
        if user_id not in self.active_connections:
            print(f"❌ 사용자 {user_id}가 연결되어 있지 않음")
            logger.warning(f"User {user_id} not connected")
            return False
        
        connections_count = len(self.active_connections[user_id])
        print(f"🔗 활성 연결 개수: {connections_count}")
        
        message_str = json.dumps(message, ensure_ascii=False)
        disconnected_connections = []
        sent_successfully = 0
        
        for i, connection in enumerate(self.active_connections[user_id]):
            try:
                print(f"📤 연결 #{i+1}에 메시지 전송 중...")
                await connection.send_text(message_str)
                sent_successfully += 1
                print(f"✅ 연결 #{i+1} 전송 성공")
            except Exception as e:
                print(f"❌ 연결 #{i+1} 전송 실패: {e}")
                logger.warning(f"Failed to send message to user {user_id}: {e}")
                disconnected_connections.append(connection)
        
        # 끊어진 연결 정리
        for connection in disconnected_connections:
            await self.disconnect(connection)
        
        success = len(disconnected_connections) == 0
        print(f"📊 전송 결과: {sent_successfully}/{connections_count} 성공, 상태: {'성공' if success else '실패'}")
        
        return success
    
    async def broadcast_to_room(self, room_id: str, message: dict, exclude_user: Optional[int] = None):
        """룸의 모든 사용자에게 메시지 브로드캐스트"""
        print(f"📡 룸 브로드캐스트 시작 - 룸: {room_id}")
        print(f"📝 메시지 타입: {message.get('type', 'unknown')}")
        
        # 룸 존재 여부 확인 및 안전한 멤버 획득
        room_members = self.rooms.get(room_id)
        if room_members is None:
            print(f"❌ 룸 {room_id}이 존재하지 않음")
            logger.warning(f"Room {room_id} not found")
            return 0
        
        # 룸 멤버가 비어있는지 확인
        if not room_members:
            print(f"❌ 룸 {room_id}에 멤버가 없음")
            logger.warning(f"Room {room_id} has no members")
            return 0
        
        # 멤버 리스트를 복사하여 순회 중 변경에 대비
        members_list = list(room_members)
        print(f"👥 룸 멤버 수: {len(members_list)}, 멤버: {members_list}")
        
        if exclude_user:
            print(f"🚫 제외할 사용자: {exclude_user}")
        
        message["room_id"] = room_id
        sent_count = 0
        failed_users = []
        
        for user_id in members_list:
            if exclude_user and user_id == exclude_user:
                print(f"⏭️ 사용자 {user_id} 제외")
                continue
            
            print(f"👤 사용자 {user_id}에게 메시지 전송 중...")
            success = await self.send_personal_message(message, user_id)
            if success:
                sent_count += 1
                print(f"✅ 사용자 {user_id} 전송 성공")
            else:
                failed_users.append(user_id)
                print(f"❌ 사용자 {user_id} 전송 실패")
        
        if failed_users:
            print(f"🔴 전송 실패한 사용자들: {failed_users}")
            logger.warning(f"Failed to send message to users: {failed_users} in room {room_id}")
        
        print(f"📊 브로드캐스트 완료 - {sent_count}/{len(members_list)} 사용자에게 전송 성공")
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
        try:
            # 룸에서 사용자 제거
            if room_id in self.rooms:
                self.rooms[room_id].discard(user_id)
                if not self.rooms[room_id]:  # 빈 룸 정리
                    del self.rooms[room_id]
            
            # 사용자의 룸 목록에서 제거
            if user_id in self.user_rooms:
                self.user_rooms[user_id].discard(room_id)
                if not self.user_rooms[user_id]:
                    del self.user_rooms[user_id]
            
            logger.info(f"User {user_id} left room {room_id}")
            
            # 룸 나감 확인 메시지 (사용자가 여전히 연결되어 있는 경우에만)
            if self.is_user_online(user_id):
                await self.send_personal_message({
                    "type": "room_left",
                    "room_id": room_id,
                    "message": f"룸 {room_id}에서 나갔습니다.",
                    "timestamp": datetime.utcnow().isoformat()
                }, user_id)
        except Exception as e:
            logger.error(f"Error leaving room {room_id} for user {user_id}: {e}")
    
    async def _leave_all_rooms(self, user_id: int):
        """사용자를 모든 룸에서 제거"""
        try:
            if user_id not in self.user_rooms:
                return
            
            # 룸 리스트를 복사하여 순회 중 변경에 대비
            rooms_to_leave = list(self.user_rooms[user_id])
            logger.info(f"User {user_id} leaving {len(rooms_to_leave)} rooms: {rooms_to_leave}")
            
            for room_id in rooms_to_leave:
                try:
                    await self.leave_room(user_id, room_id)
                except Exception as e:
                    logger.error(f"Error leaving room {room_id} for user {user_id}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error leaving all rooms for user {user_id}: {e}")
    
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