from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TaskCreateRequest(BaseModel):
    title: str
    assignee_id: Optional[int] = None  # 담당자 ID, 선택적
    parent_task_id: Optional[int] = None
    priority: str               # "low"|"medium"|"high"
    start_date: datetime
    due_date: datetime
    project_id: int

    class Config:
        orm_mode = True

class TaskResponse(BaseModel):
    task_id: int
    project_id: int
    parent_task_id: Optional[int]
    title: str
    assignee_id: Optional[int] = None  # 담당자 ID, 선택적
    priority: str
    start_date: datetime
    due_date: datetime
    status: str
    updated_at: Optional[datetime]
    description: Optional[str] = None  # 업무 설명
    assignee_name: Optional[str] = None  # 담당자 이름
    class Config:
        orm_mode = True
