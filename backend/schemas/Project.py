# backend/routers/schemas/project_member.py
from pydantic import BaseModel

class ProjectMemberResponse(BaseModel):
    user_id: int
    name: str

    class Config:
        from_attributes = True
