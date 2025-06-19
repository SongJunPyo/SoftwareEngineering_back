from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TaskCreateRequest(BaseModel):
    title: str
    assignee_id: int
    parent_task_id: Optional[int] = None
    priority: str               # "low"|"medium"|"high"
    start_date: datetime
    due_date: datetime
    project_id: int

    class Config:
        orm_mode = True

class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    assignee_id: Optional[int] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    parent_task_id: Optional[int] = None  # 상위 업무 ID
    member_ids: Optional[List[int]] = None  # 업무 멤버 ID 리스트

    class Config:
        orm_mode = True

class TaskResponse(BaseModel):
    task_id: int
    project_id: int
    parent_task_id: Optional[int]
    title: str
    assignee_id: int
    priority: str
    start_date: datetime
    due_date: datetime
    status: str
    updated_at: Optional[datetime]
    description: Optional[str] = None  # 업무 설명
    assignee_name: Optional[str] = None  # 담당자 이름
    member_ids: Optional[List[int]] = None  # 업무 멤버 ID 리스트
    
    class Config:
        orm_mode = True