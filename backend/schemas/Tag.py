from pydantic import BaseModel
from typing import List, Optional

class TagCreateRequest(BaseModel):
    tag_name: str
    project_id: int

    class Config:
        from_attributes = True

class TagUpdateRequest(BaseModel):
    tag_name: str

    class Config:
        from_attributes = True

class TagResponse(BaseModel):
    project_id: int
    tag_name: str

    class Config:
        from_attributes = True

class TaskTagCreateRequest(BaseModel):
    task_id: int
    tag_names: List[str]  # Multiple tags can be assigned to a task

    class Config:
        from_attributes = True

class TaskTagResponse(BaseModel):
    task_id: int
    tag_name: str

    class Config:
        from_attributes = True