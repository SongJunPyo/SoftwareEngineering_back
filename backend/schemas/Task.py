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
    is_parent_task: Optional[bool] = False  # 상위업무 여부

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
    is_parent_task: Optional[bool] = None  # 상위업무 여부
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
    is_parent_task: Optional[bool] = False  # 상위업무 여부
    updated_at: Optional[datetime] = None  # 생성/수정일
    description: Optional[str] = None  # 업무 설명
    assignee_name: Optional[str] = None  # 담당자 이름
    parent_task_title: Optional[str] = None  # 상위 업무 제목
    member_ids: Optional[List[int]] = None  # 업무 멤버 ID 리스트
    
    class Config:
        orm_mode = True