#!/usr/bin/env python3
"""
Deadline Notification System Test Script
테스트를 위한 마감일 알림 시스템 검증 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database.base import SessionLocal
from backend.models.task import Task
from backend.models.user import User
from backend.models.project import Project
from backend.models.logs_notification import Notification
from datetime import datetime, date, timedelta
from sqlalchemy import and_

def test_deadline_notification_logic():
    """마감일 알림 로직 테스트"""
    print("🧪 Deadline Notification System Test")
    print("=" * 50)
    
    db = SessionLocal()
    
    try:
        # 1. 데이터베이스 연결 테스트
        print("1. 데이터베이스 연결 테스트...")
        user_count = db.query(User).count()
        task_count = db.query(Task).count()
        print(f"   ✅ 사용자 수: {user_count}, 작업 수: {task_count}")
        
        # 2. 오늘 기준 테스트 데이터 확인
        today = date.today()
        print(f"\n2. 오늘 날짜: {today}")
        
        # 3. 연체된 작업 조회 테스트
        print("\n3. 연체된 작업 조회...")
        overdue_tasks = db.query(Task).filter(
            and_(
                Task.due_date < today,
                Task.status != 'completed',
                Task.assignee_id.isnot(None)
            )
        ).all()
        
        print(f"   📋 연체된 작업: {len(overdue_tasks)}개")
        for task in overdue_tasks[:3]:  # 최대 3개만 표시
            days_overdue = (today - task.due_date).days
            print(f"   - {task.title} (연체 {days_overdue}일, 담당자: {task.assignee_id})")
        
        # 4. 마감일 임박 작업 조회 테스트
        print("\n4. 마감일 임박 작업 조회...")
        
        thresholds = [1, 3, 7]
        for days in thresholds:
            target_date = today + timedelta(days=days)
            approaching_tasks = db.query(Task).filter(
                and_(
                    Task.due_date == target_date,
                    Task.status != 'completed',
                    Task.assignee_id.isnot(None)
                )
            ).all()
            
            print(f"   📅 {days}일 후 마감 ({target_date}): {len(approaching_tasks)}개")
            for task in approaching_tasks[:2]:  # 최대 2개만 표시
                print(f"   - {task.title} (담당자: {task.assignee_id})")
        
        # 5. 최근 알림 조회 테스트
        print("\n5. 최근 마감일 관련 알림 조회...")
        recent_notifications = db.query(Notification).filter(
            Notification.type.in_([
                'deadline_approaching', 'task_overdue', 
                'deadline_1day', 'deadline_3days', 'deadline_7days'
            ])
        ).order_by(Notification.created_at.desc()).limit(5).all()
        
        print(f"   🔔 최근 마감일 알림: {len(recent_notifications)}개")
        for notif in recent_notifications:
            print(f"   - {notif.type}: {notif.message[:50]}... (사용자: {notif.user_id})")
        
        # 6. 알림 중복 방지 로직 테스트
        print("\n6. 알림 중복 방지 테스트...")
        today_start = datetime.combine(today, datetime.min.time())
        tomorrow_start = today_start + timedelta(days=1)
        
        today_notifications = db.query(Notification).filter(
            and_(
                Notification.created_at >= today_start,
                Notification.created_at < tomorrow_start,
                Notification.type.in_([
                    'deadline_approaching', 'task_overdue',
                    'deadline_1day', 'deadline_3days', 'deadline_7days'
                ])
            )
        ).count()
        
        print(f"   🛡️  오늘 발송된 마감일 알림: {today_notifications}개")
        
        print("\n✅ 테스트 완료!")
        print("\n📊 시스템 상태:")
        print(f"   - 활성 사용자: {user_count}명")
        print(f"   - 총 작업: {task_count}개")
        print(f"   - 연체 작업: {len(overdue_tasks)}개")
        print(f"   - 오늘 알림: {today_notifications}개")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
    finally:
        db.close()

def main():
    """메인 함수"""
    test_deadline_notification_logic()

if __name__ == "__main__":
    main()