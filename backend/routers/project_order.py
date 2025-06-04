from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.models.project import Project
from backend.database.base import get_db
from backend.middleware.auth import verify_token

router = APIRouter(prefix="/api/v1/projects")

@router.put("/order")
def update_project_order(order_list: list, db: Session = Depends(get_db), current_user = Depends(verify_token)):
    """
    order_list: [{"project_id": 1, "order": 1}, {"project_id": 2, "order": 2}, ...]
    """
    for item in order_list:
        project = db.query(Project).filter(Project.project_id == item["project_id"], Project.owner_id == current_user.user_id).first()
        if project:
            project.order = item["order"]
    db.commit()
    return {"message": "순서 변경 완료"}

@router.put("/{project_id}/move")
def move_project(project_id: int, data: dict, db: Session = Depends(get_db), current_user = Depends(verify_token)):
    """
    data: {"workspace_id": 3}
    """
    project = db.query(Project).filter(Project.project_id == project_id, Project.owner_id == current_user.user_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    project.workspace_id = data["workspace_id"]
    db.commit()
    db.refresh(project)
    return {"project_id": project.project_id, "workspace_id": project.workspace_id, "title": project.title} 