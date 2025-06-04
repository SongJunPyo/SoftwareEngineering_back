from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from backend.models.workspace import Workspace
from backend.models.user import User
from backend.database.base import get_db
from backend.middleware.auth import verify_token
from typing import List, Dict, Any

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspace"])

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_workspace(
    data: Dict[str, Any] = Body(...), 
    db: Session = Depends(get_db), 
    current_user: User = Depends(verify_token)
):
    """워크스페이스 생성"""
    name = data.get("name")
    description = data.get("description", "")
    
    if not name:
        raise HTTPException(status_code=400, detail="워크스페이스 이름은 필수입니다.")
    
    # 이름 중복 확인 (같은 사용자 내에서)
    existing_workspace = db.query(Workspace).filter(
        Workspace.user_id == current_user.user_id,
        Workspace.name == name
    ).first()
    
    if existing_workspace:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 같은 이름의 워크스페이스가 존재합니다."
        )
    
    new_workspace = Workspace(
        name=name,
        description=description,
        user_id=current_user.user_id
    )
    
    db.add(new_workspace)
    db.commit()
    db.refresh(new_workspace)
    
    return {
        "workspace_id": new_workspace.workspace_id,
        "name": new_workspace.name,
        "description": new_workspace.description,
        "created_at": new_workspace.created_at
    }

@router.get("/")
def list_workspaces(
    db: Session = Depends(get_db), 
    current_user: User = Depends(verify_token)
):
    """워크스페이스 목록 조회"""
    workspaces = db.query(Workspace).filter(
        Workspace.user_id == current_user.user_id
    ).order_by(Workspace.created_at.desc()).all()
    
    return [
        {
            "workspace_id": ws.workspace_id,
            "name": ws.name,
            "description": ws.description,
            "created_at": ws.created_at
        } 
        for ws in workspaces
    ]

@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """워크스페이스 상세 조회"""
    workspace = db.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.user_id == current_user.user_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    return {
        "workspace_id": workspace.workspace_id,
        "name": workspace.name,
        "description": workspace.description,
        "created_at": workspace.created_at
    }

@router.put("/{workspace_id}")
def update_workspace(
    workspace_id: int,
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """워크스페이스 수정"""
    workspace = db.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.user_id == current_user.user_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    name = data.get("name")
    description = data.get("description")
    
    # 이름이 변경되는 경우 중복 확인
    if name and name != workspace.name:
        existing_workspace = db.query(Workspace).filter(
            Workspace.user_id == current_user.user_id,
            Workspace.name == name,
            Workspace.workspace_id != workspace_id
        ).first()
        
        if existing_workspace:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 같은 이름의 워크스페이스가 존재합니다."
            )
        workspace.name = name
    
    if description is not None:
        workspace.description = description
    
    db.commit()
    db.refresh(workspace)
    
    return {
        "workspace_id": workspace.workspace_id,
        "name": workspace.name,
        "description": workspace.description,
        "created_at": workspace.created_at
    }

@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """워크스페이스 삭제"""
    workspace = db.query(Workspace).filter(
        Workspace.workspace_id == workspace_id,
        Workspace.user_id == current_user.user_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="워크스페이스를 찾을 수 없습니다."
        )
    
    db.delete(workspace)
    db.commit()
    
    return {"message": "워크스페이스가 성공적으로 삭제되었습니다."} 