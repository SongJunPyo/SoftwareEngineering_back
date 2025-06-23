from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from backend.models.workspace_project_order import WorkspaceProjectOrder
from backend.models.workspace import Workspace
from backend.models.project import Project, ProjectMember
from backend.models.user import User
from backend.database.base import get_db
from backend.middleware.auth import verify_token

router = APIRouter(prefix="/api/v1/workspace-project-order", tags=["Workspace Project Order"])

@router.post("/")
def add_project_to_workspace(
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """워크스페이스에 프로젝트 추가"""
    workspace_id = data.get("workspace_id")
    project_id = data.get("project_id")
    project_order = data.get("project_order", 0)
    
    if not workspace_id or not project_id:
        raise HTTPException(status_code=400, detail="workspace_id와 project_id는 필수입니다.")
    
    # 워크스페이스 소유권 확인
    workspace = db.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.user_id == current_user.user_id
    ).first()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="워크스페이스를 찾을 수 없거나 접근 권한이 없습니다.")
    
    # 프로젝트 접근 권한 확인 (소유자이거나 멤버여야 함)
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    
    # 프로젝트 소유자이거나 멤버인지 확인
    is_owner = project.owner_id == current_user.user_id
    is_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first() is not None
    
    if not (is_owner or is_member):
        raise HTTPException(status_code=403, detail="프로젝트에 대한 접근 권한이 없습니다.")
    
    # 이미 해당 워크스페이스에 있는지 확인
    existing = db.query(WorkspaceProjectOrder).filter(
        WorkspaceProjectOrder.workspace_id == workspace_id,
        WorkspaceProjectOrder.project_id == project_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="이미 해당 워크스페이스에 프로젝트가 있습니다.")
    
    # 워크스페이스-프로젝트 관계 생성
    wpo = WorkspaceProjectOrder(
        workspace_id=workspace_id,
        project_id=project_id,
        project_order=project_order
    )
    
    db.add(wpo)
    db.commit()
    
    return {"message": "프로젝트가 워크스페이스에 추가되었습니다."}

@router.delete("/{workspace_id}/{project_id}")
def remove_project_from_workspace(
    workspace_id: int,
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """워크스페이스에서 프로젝트 제거"""
    # 워크스페이스 소유권 확인
    workspace = db.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.user_id == current_user.user_id
    ).first()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="워크스페이스를 찾을 수 없거나 접근 권한이 없습니다.")
    
    # 워크스페이스-프로젝트 관계 찾기
    wpo = db.query(WorkspaceProjectOrder).filter(
        WorkspaceProjectOrder.workspace_id == workspace_id,
        WorkspaceProjectOrder.project_id == project_id
    ).first()
    
    if not wpo:
        raise HTTPException(status_code=404, detail="해당 워크스페이스에 프로젝트가 없습니다.")
    
    db.delete(wpo)
    db.commit()
    
    return {"message": "프로젝트가 워크스페이스에서 제거되었습니다."}

@router.put("/order")
def update_project_order(
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """워크스페이스 내 프로젝트 순서 업데이트"""
    workspace_id = data.get("workspace_id")
    project_orders = data.get("project_orders", [])  # [{"project_id": 1, "order": 0}, ...]
    
    if not workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id는 필수입니다.")
    
    # 워크스페이스 소유권 확인
    workspace = db.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.user_id == current_user.user_id
    ).first()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="워크스페이스를 찾을 수 없거나 접근 권한이 없습니다.")
    
    # 순서 업데이트
    for order_data in project_orders:
        project_id = order_data.get("project_id")
        new_order = order_data.get("order")
        
        wpo = db.query(WorkspaceProjectOrder).filter(
            WorkspaceProjectOrder.workspace_id == workspace_id,
            WorkspaceProjectOrder.project_id == project_id
        ).first()
        
        if wpo:
            wpo.project_order = new_order
    
    db.commit()
    
    return {"message": "프로젝트 순서가 업데이트되었습니다."}

@router.get("/workspace/{workspace_id}/projects")
def get_workspace_projects(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """워크스페이스의 프로젝트 목록 조회 (순서대로)"""
    # 워크스페이스 소유권 확인
    workspace = db.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.user_id == current_user.user_id
    ).first()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="워크스페이스를 찾을 수 없거나 접근 권한이 없습니다.")
    
    # 워크스페이스의 프로젝트들을 순서대로 조회
    results = db.query(WorkspaceProjectOrder, Project).join(
        Project, WorkspaceProjectOrder.project_id == Project.project_id
    ).filter(
        WorkspaceProjectOrder.workspace_id == workspace_id
    ).order_by(WorkspaceProjectOrder.project_order).all()
    
    projects = []
    for wpo, project in results:
        # 사용자 역할 확인
        role = None
        if project.owner_id == current_user.user_id:
            role = "owner"
        else:
            member = db.query(ProjectMember).filter(
                ProjectMember.project_id == project.project_id,
                ProjectMember.user_id == current_user.user_id
            ).first()
            role = member.role if member else None
        
        projects.append({
            "project_id": project.project_id,
            "title": project.title,
            "description": project.description,
            "status": project.status,
            "owner_id": project.owner_id,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "project_order": wpo.project_order,
            "user_role": role
        })
    
    return projects
