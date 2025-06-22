from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.orm import Session
from backend.models.workspace import Workspace
from backend.models.user import User
from backend.database.base import get_db
from backend.middleware.auth import verify_token
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspace"])

class WorkspaceOrderItem(BaseModel):
    workspace_id: int
    order: int

class WorkspaceOrderRequest(BaseModel):
    workspace_orders: List[WorkspaceOrderItem]

class WorkspaceCreate(BaseModel):
    name: str
    order: Optional[int] = None

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    order: Optional[int] = None

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_workspace(
    data: WorkspaceCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(verify_token)
):
    """워크스페이스 생성"""
    name = data.name
    order = data.order
    
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
    
    # order가 지정되지 않은 경우 기존 워크스페이스 개수를 기준으로 설정 (0부터 시작)
    if order is None:
        workspace_count = db.query(Workspace).filter(
            Workspace.user_id == current_user.user_id
        ).count()
        order = workspace_count
    
    new_workspace = Workspace(
        name=name,
        user_id=current_user.user_id,
        order=order
    )
    
    db.add(new_workspace)
    db.commit()
    db.refresh(new_workspace)
    
    return {
        "workspace_id": new_workspace.workspace_id,
        "name": new_workspace.name,
        "order": new_workspace.order
    }

@router.get("/")
def list_workspaces(
    db: Session = Depends(get_db), 
    current_user: User = Depends(verify_token)
):
    """워크스페이스 목록 조회"""
    workspaces = db.query(Workspace).filter(
        Workspace.user_id == current_user.user_id
    ).order_by(Workspace.order.asc()).all()
    
    return [
        {
            "workspace_id": ws.workspace_id,
            "name": ws.name,
            "order": ws.order
        } 
        for ws in workspaces
    ]

@router.get("/default")
def get_default_workspace(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """기본 워크스페이스(order=1) 조회"""
    default_workspace = db.query(Workspace).filter(
        Workspace.user_id == current_user.user_id,
        Workspace.order == 1
    ).first()
    
    if not default_workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="기본 워크스페이스를 찾을 수 없습니다."
        )
    
    return {
        "workspace_id": default_workspace.workspace_id,
        "name": default_workspace.name,
        "order": default_workspace.order
    }

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
        "order": workspace.order
    }

@router.put("/{workspace_id}")
def update_workspace(
    workspace_id: int,
    data: WorkspaceUpdate,
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
    
    name = data.name
    order = data.order
    
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
    
    if order is not None:
        workspace.order = order
    
    db.commit()
    db.refresh(workspace)
    
    return {
        "workspace_id": workspace.workspace_id,
        "name": workspace.name,
        "order": workspace.order
    }

@router.patch("/reorder")
def update_workspace_order(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """워크스페이스 순서 업데이트"""
    try:
        print(f"엔드포인트 진입!")
        print(f"받은 data: {data}")
        print(f"data 타입: {type(data)}")
        workspace_orders = data.get("workspace_orders", [])
        print(f"workspace_orders: {workspace_orders}")
        print(f"workspace_orders 타입: {type(workspace_orders)}")
        
        if not workspace_orders:
            raise HTTPException(status_code=400, detail="workspace_orders가 비어있습니다")
        
        # 현재 사용자의 워크스페이스 ID 목록을 가져와서 권한 검증
        user_workspace_ids = set(
            ws.workspace_id for ws in 
            db.query(Workspace.workspace_id).filter(Workspace.user_id == current_user.user_id).all()
        )
        
        
        # 순서 업데이트
        updated_count = 0
        not_found_workspaces = []
        
        for order_item in workspace_orders:
            workspace_id = order_item.get("workspace_id") if isinstance(order_item, dict) else order_item.workspace_id
            new_order = order_item.get("order") if isinstance(order_item, dict) else order_item.order
            
            
            # 권한 확인
            if workspace_id not in user_workspace_ids:
                not_found_workspaces.append(workspace_id)
                continue
                
            workspace = db.query(Workspace).filter(
                Workspace.workspace_id == workspace_id,
                Workspace.user_id == current_user.user_id
            ).first()
            
            if workspace:
                workspace.order = new_order
                updated_count += 1
            else:
                not_found_workspaces.append(workspace_id)
        
        
        db.commit()
        
        result = {
            "message": f"워크스페이스 순서가 업데이트되었습니다. ({updated_count}개)",
            "updated_count": updated_count,
            "total_requested": len(workspace_orders)
        }
        
        if not_found_workspaces:
            result["not_found_workspaces"] = not_found_workspaces
            
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"워크스페이스 순서 업데이트 실패: {str(e)}"
        )

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
    
    # 🔒 워크스페이스에 프로젝트가 있는지 확인
    from backend.models.workspace_project_order import WorkspaceProjectOrder
    projects_in_workspace = db.query(WorkspaceProjectOrder).filter(
        WorkspaceProjectOrder.workspace_id == workspace_id
    ).count()
    
    if projects_in_workspace > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"워크스페이스에 {projects_in_workspace}개의 프로젝트가 있습니다. 모든 프로젝트를 삭제하거나 다른 워크스페이스로 이동한 후 삭제해주세요."
        )
    
    db.delete(workspace)
    db.commit()
    
    return {"message": "워크스페이스가 성공적으로 삭제되었습니다."}
