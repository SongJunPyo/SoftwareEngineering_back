from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from backend.models.project import Project
from backend.models.workspace import Workspace
from backend.models.user import User
from backend.database.base import get_db
from backend.middleware.auth import verify_token
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/api/v1/projects", tags=["Project"])

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_project(
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 생성"""
    title = data.get("title")
    description = data.get("description", "")
    workspace_id = data.get("workspace_id")
    
    if not title:
        raise HTTPException(status_code=400, detail="프로젝트 제목은 필수입니다.")
    
    if not workspace_id:
        raise HTTPException(status_code=400, detail="워크스페이스 ID는 필수입니다.")
    
    # 워크스페이스 소유권 확인
    workspace = db.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.user_id == current_user.user_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없거나 접근 권한이 없습니다."
        )
    
    # 같은 워크스페이스 내 제목 중복 확인
    existing_project = db.query(Project).filter(
        Project.workspace_id == workspace_id,
        Project.title == title
    ).first()
    
    if existing_project:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="같은 워크스페이스에 이미 같은 제목의 프로젝트가 존재합니다."
        )
    
    new_project = Project(
        title=title,
        description=description,
        workspace_id=workspace_id,
        owner_id=current_user.user_id
    )
    
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    return {
        "project_id": new_project.project_id,
        "title": new_project.title,
        "description": new_project.description,
        "workspace_id": new_project.workspace_id,
        "created_at": new_project.created_at
    }

@router.get("/")
def list_projects(
    workspace_id: Optional[int] = Query(None, description="워크스페이스로 필터링"),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 목록 조회"""
    query = db.query(Project).filter(Project.owner_id == current_user.user_id)
    
    # 워크스페이스 필터링
    if workspace_id:
        # 워크스페이스 접근 권한 확인
        workspace = db.query(Workspace).filter(
            Workspace.workspace_id == workspace_id,
            Workspace.user_id == current_user.user_id
        ).first()
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="워크스페이스를 찾을 수 없거나 접근 권한이 없습니다."
            )
        
        query = query.filter(Project.workspace_id == workspace_id)
    
    projects = query.order_by(Project.created_at.desc()).all()
    
    return [
        {
            "project_id": p.project_id,
            "title": p.title,
            "description": p.description,
            "workspace_id": p.workspace_id,
            "created_at": p.created_at
        }
        for p in projects
    ]

@router.get("/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 상세 조회"""
    project = db.query(Project).filter(
        Project.project_id == project_id,
        Project.owner_id == current_user.user_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    
    return {
        "project_id": project.project_id,
        "title": project.title,
        "description": project.description,
        "workspace_id": project.workspace_id,
        "created_at": project.created_at
    }

@router.put("/{project_id}")
def update_project(
    project_id: int,
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 수정"""
    project = db.query(Project).filter(
        Project.project_id == project_id,
        Project.owner_id == current_user.user_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    
    title = data.get("title")
    description = data.get("description")
    workspace_id = data.get("workspace_id")
    
    # 워크스페이스가 변경되는 경우 권한 확인
    if workspace_id and workspace_id != project.workspace_id:
        workspace = db.query(Workspace).filter(
            Workspace.workspace_id == workspace_id,
            Workspace.user_id == current_user.user_id
        ).first()
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="워크스페이스를 찾을 수 없거나 접근 권한이 없습니다."
            )
        project.workspace_id = workspace_id
    
    # 제목이 변경되는 경우 중복 확인
    if title and title != project.title:
        existing_project = db.query(Project).filter(
            Project.workspace_id == project.workspace_id,
            Project.title == title,
            Project.project_id != project_id
        ).first()
        
        if existing_project:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="같은 워크스페이스에 이미 같은 제목의 프로젝트가 존재합니다."
            )
        project.title = title
    
    if description is not None:
        project.description = description
    
    db.commit()
    db.refresh(project)
    
    return {
        "project_id": project.project_id,
        "title": project.title,
        "description": project.description,
        "workspace_id": project.workspace_id,
        "created_at": project.created_at
    }

@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 삭제"""
    project = db.query(Project).filter(
        Project.project_id == project_id,
        Project.owner_id == current_user.user_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    
    db.delete(project)
    db.commit()
    
    return {"message": "프로젝트가 성공적으로 삭제되었습니다."} 