"""
Enhanced Deadline Notification System
====================================

이 모듈은 작업 마감일에 대한 포괄적인 알림 시스템을 제공합니다.

주요 기능:
1. 다중 마감일 임계값 알림 (1일, 3일, 7일 전)
2. 연체된 작업에 대한 알림
3. 상세한 알림 메시지 (우선순위, 연체 일수 포함)
4. 중복 알림 방지 시스템
5. 효율적인 스케줄링 (매시간 정각 실행)

알림 타입:
- deadline_approaching: 일반적인 마감일 임박 알림
- task_overdue: 연체된 작업 알림  
- deadline_1day: 1일 전 알림
- deadline_3days: 3일 전 알림
- deadline_7days: 7일 전 알림

작성자: Claude Code Enhancement
최종 수정: 2025-06-22
"""

from backend.database.base import SessionLocal
from backend.models.task import Task
from backend.models.logs_notification import Notification
from backend.routers.notifications import create_notification
from datetime import datetime, timedelta, date
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import and_, or_
import asyncio
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def send_deadline_notifications():
    """다양한 마감일 임박 알림과 연체 알림을 처리하는 통합 함수"""
    try:
        db = SessionLocal()
        today = date.today()
        
        # 연체된 업무 처리
        process_overdue_tasks(db, today)
        
        # 마감일 임박 알림 처리 (1일, 3일, 7일 전)
        process_approaching_deadlines(db, today)
        
        db.close()
        logger.info("Deadline notification processing completed successfully")
    except Exception as e:
        logger.error(f"[DEADLINE ERROR] {e}")
        if 'db' in locals():
            db.close()


def process_overdue_tasks(db, today):
    """연체된 업무에 대한 알림 처리"""
    try:
        # 연체된 업무 조회 (완료되지 않은 것만)
        overdue_tasks = db.query(Task).filter(
            and_(
                Task.due_date < today,
                Task.status != 'completed',
                or_(Task.assignee_id.isnot(None))
            )
        ).all()
        
        logger.info(f"Found {len(overdue_tasks)} overdue tasks")
        
        for task in overdue_tasks:
            if task.assignee_id:
                # 오늘 이미 연체 알림을 보냈는지 확인
                existing_notification = check_existing_notification(
                    db, task.assignee_id, task.task_id, "task_overdue", today
                )
                
                if not existing_notification:
                    days_overdue = (today - task.due_date).days
                    
                    message = create_overdue_message(task.title, days_overdue, task.priority)
                    
                    logger.info(f"Sending overdue notification for task {task.task_id} to user {task.assignee_id}")
                    asyncio.run(create_notification(
                        db=db,
                        user_id=task.assignee_id,
                        type="task_overdue",
                        message=message,
                        channel="task",
                        related_id=task.task_id,
                        project_id=task.project_id
                    ))
                    
    except Exception as e:
        logger.error(f"Error processing overdue tasks: {e}")


def process_approaching_deadlines(db, today):
    """마감일 임박 알림 처리 (1일, 3일, 7일 전)"""
    deadline_thresholds = [
        {"days": 1, "type": "deadline_1day", "description": "1일"},
        {"days": 3, "type": "deadline_3days", "description": "3일"},
        {"days": 7, "type": "deadline_7days", "description": "1주일"}
    ]
    
    try:
        for threshold in deadline_thresholds:
            target_date = today + timedelta(days=threshold["days"])
            
            # 해당 날짜에 마감되는 업무 조회 (완료되지 않은 것만)
            approaching_tasks = db.query(Task).filter(
                and_(
                    Task.due_date == target_date,
                    Task.status != 'completed',
                    or_(Task.assignee_id.isnot(None))
                )
            ).all()
            
            logger.info(f"Found {len(approaching_tasks)} tasks approaching deadline in {threshold['days']} days")
            
            for task in approaching_tasks:
                if task.assignee_id:
                    # 오늘 이미 해당 임계값에 대한 알림을 보냈는지 확인
                    existing_notification = check_existing_notification(
                        db, task.assignee_id, task.task_id, threshold["type"], today
                    )
                    
                    if not existing_notification:
                        message = create_approaching_deadline_message(
                            task.title, threshold["description"], task.priority, task.due_date
                        )
                        
                        logger.info(f"Sending {threshold['days']}-day deadline notification for task {task.task_id} to user {task.assignee_id}")
                        asyncio.run(create_notification(
                            db=db,
                            user_id=task.assignee_id,
                            type="deadline_approaching",
                            message=message,
                            channel="task",
                            related_id=task.task_id,
                            project_id=task.project_id
                        ))
                        
    except Exception as e:
        logger.error(f"Error processing approaching deadlines: {e}")


def create_overdue_message(task_title, days_overdue, priority):
    """연체 알림 메시지 생성"""
    priority_emoji = get_priority_emoji(priority)
    
    if days_overdue == 1:
        return f"{priority_emoji} '{task_title}' 업무가 어제 마감일을 넘겼습니다. 빠른 처리가 필요합니다."
    else:
        return f"{priority_emoji} '{task_title}' 업무가 {days_overdue}일째 연체 중입니다. 즉시 확인이 필요합니다."


def create_approaching_deadline_message(task_title, time_description, priority, due_date):
    """마감일 임박 알림 메시지 생성"""
    priority_emoji = get_priority_emoji(priority)
    due_date_str = due_date.strftime("%m월 %d일")
    
    return f"{priority_emoji} '{task_title}' 업무의 마감일이 {time_description} 남았습니다. (마감일: {due_date_str})"


def get_priority_emoji(priority):
    """우선순위에 따른 이모지 반환"""
    priority_map = {
        "high": "🔴",
        "medium": "🟡",
        "low": "🟢"
    }
    return priority_map.get(priority, "📋")


def check_existing_notification(db, user_id, task_id, notification_type, today):
    """오늘 이미 해당 유형의 알림이 발송되었는지 확인"""
    today_start = datetime.combine(today, datetime.min.time())
    tomorrow_start = today_start + timedelta(days=1)
    
    return db.query(Notification).filter(
        and_(
            Notification.user_id == user_id,
            Notification.related_id == task_id,
            Notification.type.in_([notification_type, "deadline_approaching", "task_overdue"]),
            Notification.created_at >= today_start,
            Notification.created_at < tomorrow_start
        )
    ).first()

# 서버 로딩 시 즉시 한 번 실행
send_deadline_notifications()

# 스케줄러 설정 - 매시간 정각에 실행 (더 효율적)
scheduler.add_job(
    send_deadline_notifications, 
    'cron', 
    hour='*',  # 매시간
    minute=0,  # 정각
    second=0
)

# 개발/테스트용 - 매 5분마다 실행 (필요시 주석 해제)
# scheduler.add_job(send_deadline_notifications, 'interval', minutes=5)

scheduler.start()
logger.info("Deadline notification scheduler started successfully") 