from pydantic import BaseModel
from datetime import datetime

class LogResponse(BaseModel):
    log_id: int
    user_id: int
    entity_type: str
    entity_id: int
    action: str
    project_id: int = None
    timestamp: datetime

    class Config:
        orm_mode = True 