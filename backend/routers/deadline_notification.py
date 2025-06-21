from backend.database.base import SessionLocal
from backend.models.task import Task, TaskMember
from backend.routers.notifications import create_notification
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio

scheduler = BackgroundScheduler()

def send_deadline_notifications():
    try:
        db = SessionLocal()
        now = datetime.now()
        soon = now + timedelta(days=1)
        tasks = db.query(Task).filter(Task.due_date <= soon, Task.due_date > now).all()
        print(f"Found {len(tasks)} tasks")
        for task in tasks:
            members = db.query(TaskMember).filter(TaskMember.task_id == task.task_id).all()
            print(f"Task {task.task_id} has {len(members)} members")
            for member in members:
                # 이미 알림이 갔는지 체크하는 로직이 필요하다면 추가
                asyncio.run(create_notification(
                    db=db,
                    user_id=member.user_id,
                    type="deadline",
                    message=f"'{task.title}' 태스크의 마감일이 24시간 이내입니다.",
                    channel="task",
                    related_id=task.task_id
                ))
        db.commit()
        db.close()
    except Exception as e:
        print("[DEADLINE ERROR]", e)

# 서버 로딩 시 즉시 한 번 실행
send_deadline_notifications()

scheduler.add_job(send_deadline_notifications, 'interval', minutes=1)
scheduler.start() 