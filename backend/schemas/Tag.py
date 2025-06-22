from pydantic import BaseModel
from typing import List, Optional

class TagBase(BaseModel):
    tag_name: str

class TagCreateRequest(TagBase):
    project_id: int

    class Config:
        from_attributes = True

class TagUpdateRequest(TagBase):
    pass

class TagResponse(TagBase):
    project_id: int
    
    class Config:
        orm_mode = True

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