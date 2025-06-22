from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from backend.models.project import Project, ProjectMember
from backend.models.workspace import Workspace
from backend.models.workspace_project_order import WorkspaceProjectOrder
from backend.models.user import User
from backend.database.base import get_db
from backend.middleware.auth import verify_token
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/projects", tags=["Project"])

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_project(
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 생성"""
    try:
        title = data.get("title")
        description = data.get("description", "")
        workspace_id = data.get("workspace_id")  # 선택적으로 워크스페이스에 추가
        
        if not title:
            raise HTTPException(status_code=400, detail="프로젝트 제목은 필수입니다.")
        
        # 워크스페이스 결정 및 권한 확인
        if workspace_id:
            # 지정된 워크스페이스의 소유권 확인
            workspace = db.query(Workspace).filter(
                Workspace.workspace_id == workspace_id,
                Workspace.user_id == current_user.user_id
            ).first()
            
            if not workspace:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="워크스페이스를 찾을 수 없거나 접근 권한이 없습니다."
                )
            target_workspace_id = workspace_id
        else:
            # workspace_id가 없으면 사용자의 기본 워크스페이스(order=1) 사용
            default_workspace = db.query(Workspace).filter(
                Workspace.user_id == current_user.user_id,
                Workspace.order == 1
            ).first()
            
            if not default_workspace:
                # 기본 워크스페이스가 없으면 생성
                default_workspace = Workspace(
                    user_id=current_user.user_id,
                    name="기본 워크스페이스",
                    order=1
                )
                db.add(default_workspace)
                db.flush()  # ID를 얻기 위해 flush
            
            target_workspace_id = default_workspace.workspace_id
        
        # 프로젝트 생성 (workspace_id 필드 제거됨)
        new_project = Project(
            title=title,
            description=description,
            owner_id=current_user.user_id
        )
        
        db.add(new_project)
        db.flush()  # ID를 얻기 위해 flush
        
        # 프로젝트 생성자를 자동으로 소유자로 멤버 테이블에 추가
        project_owner = ProjectMember(
            project_id=new_project.project_id,
            user_id=current_user.user_id,
            role="owner"
        )
        
        db.add(project_owner)
        
        # 해당 워크스페이스의 프로젝트 개수를 세어서 순서 결정
        project_count = db.query(WorkspaceProjectOrder).filter(
            WorkspaceProjectOrder.workspace_id == target_workspace_id
        ).count()
        
        # 워크스페이스-프로젝트 관계 생성
        wpo = WorkspaceProjectOrder(
            workspace_id=target_workspace_id,
            project_id=new_project.project_id,
            project_order=project_count
        )
        db.add(wpo)
        
        # 모든 변경사항 커밋
        db.commit()
        db.refresh(new_project)
        
        return {
            "project_id": new_project.project_id,
            "title": new_project.title,
            "description": new_project.description,
            "workspace_id": target_workspace_id,  # 실제 연결된 workspace_id 반환
            "created_at": new_project.created_at
        }
    except Exception as e:
        db.rollback()
        import traceback
        print(f"프로젝트 생성 오류: {str(e)}")
        print(f"트레이스백: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"프로젝트 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/")
def list_projects(
    workspace_id: Optional[int] = Query(None, description="워크스페이스로 필터링 (-1시 독립 프로젝트)"),
    include_independent: bool = Query(False, description="독립 프로젝트 포함 여부"),
    include_member_projects: bool = Query(False, description="멤버인 프로젝트도 포함 여부"),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 목록 조회"""
    if include_member_projects:
        # 소유하거나 멤버인 모든 프로젝트 조회
        from sqlalchemy.orm import aliased
        member_alias = aliased(ProjectMember)
        
        query = db.query(Project).outerjoin(
            member_alias, 
            (Project.project_id == member_alias.project_id) & 
            (member_alias.user_id == current_user.user_id)
        ).filter(
            (Project.owner_id == current_user.user_id) | 
            (member_alias.user_id == current_user.user_id)
        )
    else:
        # 기존 로직: 소유한 프로젝트만 조회
        query = db.query(Project).filter(Project.owner_id == current_user.user_id)
    
    # 워크스페이스 필터링
    if workspace_id is not None:
        if workspace_id == -1:
            # workspace_id가 -1이면 독립 프로젝트들만 조회 (어떤 워크스페이스에도 속하지 않는 프로젝트)
            workspace_project_ids = db.query(WorkspaceProjectOrder.project_id).subquery()
            query = query.filter(~Project.project_id.in_(workspace_project_ids))
        else:
            # 특정 워크스페이스의 프로젝트만 조회
            workspace = db.query(Workspace).filter(
                Workspace.workspace_id == workspace_id,
                Workspace.user_id == current_user.user_id
            ).first()
            
            if not workspace:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="워크스페이스를 찾을 수 없거나 접근 권한이 없습니다."
                )
            
            # 해당 워크스페이스에 속한 프로젝트들만 조회
            workspace_project_ids = db.query(WorkspaceProjectOrder.project_id).filter(
                WorkspaceProjectOrder.workspace_id == workspace_id
            ).subquery()
            query = query.filter(Project.project_id.in_(workspace_project_ids))
    elif not include_independent:
        # 워크스페이스에 속한 프로젝트만 조회 (기본 동작)
        workspace_project_ids = db.query(WorkspaceProjectOrder.project_id).subquery()
        query = query.filter(Project.project_id.in_(workspace_project_ids))
    
    projects = query.order_by(Project.created_at.desc()).all()
    
    result = []
    for p in projects:
        # 멤버인 프로젝트의 경우 역할 정보도 포함
        role = None
        workspace_info = None
        
        if include_member_projects:
            if p.owner_id == current_user.user_id:
                role = "owner"
            else:
                member = db.query(ProjectMember).filter(
                    ProjectMember.project_id == p.project_id,
                    ProjectMember.user_id == current_user.user_id
                ).first()
                role = member.role if member else None
        
        # 프로젝트가 속한 워크스페이스 정보 조회 (있는 경우)
        if workspace_id != -1:  # 독립 프로젝트 조회가 아닌 경우
            wpo = db.query(WorkspaceProjectOrder).filter(
                WorkspaceProjectOrder.project_id == p.project_id
            ).first()
            workspace_info = wpo.workspace_id if wpo else None
        
        project_data = {
            "project_id": p.project_id,
            "title": p.title,
            "description": p.description,
            "workspace_id": workspace_info,
            "created_at": p.created_at
        }
        
        if include_member_projects and role:
            project_data["user_role"] = role
            
        result.append(project_data)
    
    return result

@router.get("/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 상세 조회"""
    # 멤버 권한도 확인 (소유자가 아니어도 멤버이면 조회 가능)
    project = db.query(Project).filter(Project.project_id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    
    # 소유자이거나 멤버인지 확인
    is_owner = project.owner_id == current_user.user_id
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if not is_owner and not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="프로젝트에 접근할 권한이 없습니다."
        )
    
    # 프로젝트가 속한 워크스페이스 조회
    wpo = db.query(WorkspaceProjectOrder).filter(
        WorkspaceProjectOrder.project_id == project_id
    ).first()
    workspace_id = wpo.workspace_id if wpo else None
    
    return {
        "project_id": project.project_id,
        "title": project.title,
        "description": project.description,
        "workspace_id": workspace_id,
        "created_at": project.created_at,
        "user_role": "owner" if is_owner else (member.role if member else None)
    }

@router.put("/{project_id}")
def update_project(
    project_id: int,
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 수정"""
    # 소유자이거나 관리자 이상 권한 확인
    project = db.query(Project).filter(Project.project_id == project_id).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    
    # 권한 확인 (소유자이거나 admin 이상)
    is_owner = project.owner_id == current_user.user_id
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if not is_owner and (not member or member.role not in ["admin", "owner"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="프로젝트 수정 권한이 없습니다."
        )
    
    title = data.get("title")
    description = data.get("description")
    
    # 제목이 변경되는 경우 업데이트
    if title and title != project.title:
        project.title = title
    
    if description is not None:
        project.description = description
    
    # updated_at 갱신
    project.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(project)
    
    # 프로젝트가 속한 워크스페이스 조회
    wpo = db.query(WorkspaceProjectOrder).filter(
        WorkspaceProjectOrder.project_id == project_id
    ).first()
    workspace_id = wpo.workspace_id if wpo else None
    
    return {
        "project_id": project.project_id,
        "title": project.title,
        "description": project.description,
        "workspace_id": workspace_id,
        "created_at": project.created_at,
        "updated_at": project.updated_at
    }

@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """프로젝트 삭제"""
    try:
        project = db.query(Project).filter(Project.project_id == project_id).first()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="프로젝트를 찾을 수 없습니다."
            )
        
        # 소유자만 프로젝트 삭제 가능
        if project.owner_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="프로젝트 소유자만 삭제할 수 있습니다."
            )
        
        # 1. 프로젝트 멤버 삭제 (외래키 제약 조건 때문에 먼저 삭제)
        db.query(ProjectMember).filter(ProjectMember.project_id == project_id).delete()
        
        # 2. 워크스페이스-프로젝트 관계 삭제 (CASCADE 설정되어 있어야 하지만 명시적으로 삭제)
        db.query(WorkspaceProjectOrder).filter(WorkspaceProjectOrder.project_id == project_id).delete()
        
        # 3. 프로젝트 초대 삭제 (있는 경우)
        from backend.models.project_invitation import ProjectInvitation
        db.query(ProjectInvitation).filter(ProjectInvitation.project_id == project_id).delete()
        
        # 4. 프로젝트 삭제
        db.delete(project)
        db.commit()
        
        return {"message": "프로젝트가 성공적으로 삭제되었습니다."}
    
    except Exception as e:
        db.rollback()
        import traceback
        print(f"프로젝트 삭제 오류: {str(e)}")
        print(f"트레이스백: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"프로젝트 삭제 중 오류가 발생했습니다: {str(e)}"
        ) 
