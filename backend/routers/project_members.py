from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
import os
from datetime import datetime, timezone
from backend.database.base import get_db
from backend.middleware.auth import verify_token
from backend.models.project_invitation import ProjectInvitation
from backend.models.project import ProjectMember, Project
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.models.workspace_project_order import WorkspaceProjectOrder

router = APIRouter(prefix="/api/v1/projects", tags=["project_members"])

# 이메일 설정
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=587,
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_FROM_NAME="Planora 팀",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)

class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"  # 기본값: member

@router.post("/{project_id}/invite")
async def invite_user(
    project_id: int,
    invite_data: InviteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # 역할 유효성 검증
    if invite_data.role not in ["viewer", "member", "admin", "owner"]:
        raise HTTPException(status_code=400, detail="유효하지 않은 권한입니다")
    
    # 프로젝트 권한 확인
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    
    # 현재 사용자가 프로젝트 멤버인지 확인
    current_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if not current_member or current_member.role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="관리자 이상 권한이 필요합니다")
    
    # 관리자는 admin 권한으로 초대할 수 없음 (owner만 가능)
    if current_member.role == "admin" and invite_data.role == "admin":
        raise HTTPException(status_code=403, detail="소유자만 관리자를 초대할 수 있습니다")
    
    # 이미 멤버인지 확인 (이메일로 사용자 찾기)
    invited_user = db.query(User).filter(User.email == invite_data.email).first()
    if invited_user:
        existing_member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == invited_user.user_id
        ).first()
    else:
        existing_member = None
    
    if existing_member:
        raise HTTPException(status_code=400, detail="이미 프로젝트 멤버입니다")
    
    # 초대 생성
    invitation = ProjectInvitation(
        project_id=project_id,
        email=invite_data.email,
        invited_by=current_user.user_id,
        role=invite_data.role,
        status="pending"
    )
    db.add(invitation)
    db.commit()
    
    # 이메일 전송 (백그라운드 작업)
    background_tasks.add_task(
        send_invitation_email,
        invite_data.email,
        project.title,
        current_user.name,
        invitation.project_inv_id
    )
    
    return {"message": "초대장이 전송되었습니다"}

async def send_invitation_email(email: str, project_name: str, inviter_name: str, invitation_id: int):
    """실제 이메일 전송 함수"""
    # 프론트엔드 URL 설정 (환경변수 또는 기본값)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    invitation_link = f"{frontend_url}/invite/{invitation_id}"
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #333;">프로젝트 초대장</h2>
                <p>안녕하세요!</p>
                <p><strong>{inviter_name}</strong>님이 <strong>"{project_name}"</strong> 프로젝트에 초대했습니다.</p>
                <div style="margin: 30px 0;">
                    <a href="{invitation_link}" 
                       style="background-color: #facc15; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                        초대 수락하기
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    이 초대장은 7일 후 만료됩니다.
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    Planora 팀 드림
                </p>
            </div>
        </body>
    </html>
    """
    
    message = MessageSchema(
        subject=f"[Planora] {project_name} 프로젝트 초대",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)

@router.get("/invitations/{invitation_id}/info")
async def get_invitation_info(
    invitation_id: int,
    db: Session = Depends(get_db)
):
    """초대장 정보 조회 (인증 불필요)"""
    # 초대장 조회
    invitation = db.query(ProjectInvitation, Project, User).join(
        Project, ProjectInvitation.project_id == Project.project_id
    ).join(
        User, ProjectInvitation.invited_by == User.user_id
    ).filter(ProjectInvitation.project_inv_id == invitation_id).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="초대장을 찾을 수 없습니다")
    
    invitation_obj, project_obj, inviter_obj = invitation
    
    # 만료 예정일 계산 (7일 후)
    from datetime import timedelta
    is_expired = False
    expires_at = None
    
    if invitation_obj.invited_at:
        # 타임존 처리: invited_at이 naive datetime인 경우 UTC로 설정
        invited_at = invitation_obj.invited_at
        if invited_at.tzinfo is None:
            invited_at = invited_at.replace(tzinfo=timezone.utc)
        
        expires_at = invited_at + timedelta(days=7)
        current_time = datetime.now(timezone.utc)
        is_expired = current_time > expires_at
        
        # 만료된 초대는 삭제
        if is_expired and invitation_obj.status == "pending":
            db.delete(invitation_obj)
            db.commit()
            raise HTTPException(status_code=404, detail="만료된 초대장입니다")
    else:
        # invited_at이 없는 경우 (예외 상황) - 생성 시간을 현재로 설정
        invitation_obj.invited_at = datetime.now(timezone.utc)
        invited_at = invitation_obj.invited_at
        expires_at = invited_at + timedelta(days=7)
        db.commit()
    
    return {
        "invitation_id": invitation_obj.project_inv_id,
        "email": invitation_obj.email,
        "status": invitation_obj.status,
        "is_expired": is_expired,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "project": {
            "project_id": project_obj.project_id,
            "title": project_obj.title,
            "description": project_obj.description
        },
        "inviter": {
            "name": inviter_obj.name,
            "email": inviter_obj.email
        }
    }

class AcceptInvitationRequest(BaseModel):
    workspace_id: int

@router.post("/invitations/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: int,
    request: AcceptInvitationRequest,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # 1. 초대장 확인
    invitation = db.query(ProjectInvitation).filter(
        ProjectInvitation.project_inv_id == invitation_id,
        ProjectInvitation.status == "pending"
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="유효하지 않은 초대장입니다")
    
    # 2. 이메일 일치 확인
    if current_user.email != invitation.email:
        raise HTTPException(status_code=403, detail="초대 대상자만 수락할 수 있습니다")
    
    # 3. 멤버 추가 (초대 시 지정된 role 사용)
    new_member = ProjectMember(
        project_id=invitation.project_id,
        user_id=current_user.user_id,
        role=invitation.role
    )
    db.add(new_member)
    
    # 4. 선택된 워크스페이스에 프로젝트 추가
    # 워크스페이스 권한 확인 (사용자가 소유한 워크스페이스인지)
    workspace = db.query(Workspace).filter(
        Workspace.workspace_id == request.workspace_id,
        Workspace.user_id == current_user.user_id
    ).first()
    
    if not workspace:
        raise HTTPException(status_code=403, detail="워크스페이스에 대한 권한이 없습니다")
    
    # 해당 워크스페이스에서 가장 큰 project_order 찾기
    max_order = db.query(WorkspaceProjectOrder.project_order).filter(
        WorkspaceProjectOrder.workspace_id == workspace.workspace_id
    ).order_by(WorkspaceProjectOrder.project_order.desc()).first()
    
    next_order = (max_order[0] + 1) if max_order else 1
    
    # 워크스페이스-프로젝트 관계 추가
    workspace_project = WorkspaceProjectOrder(
        workspace_id=workspace.workspace_id,
        project_id=invitation.project_id,
        project_order=next_order
    )
    db.add(workspace_project)
    
    # 5. 초대장 상태 업데이트
    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)
    
    db.commit()
    return {"message": "프로젝트에 성공적으로 참여했습니다"}

@router.get("/{project_id}/invitations")
async def get_project_invitations(
    project_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """프로젝트 초대 목록 조회"""
    # 프로젝트 권한 확인 (멤버이거나 관리자여야 함)
    is_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if not is_member:
        raise HTTPException(status_code=403, detail="프로젝트 멤버만 접근할 수 있습니다")
    
    # 관리자 이상만 초대 목록 조회 가능
    if is_member.role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="관리자 이상 권한이 필요합니다")
    
    # 만료된 초대 자동 정리 (7일 지난 것들)
    from datetime import timedelta
    current_time = datetime.now(timezone.utc)
    seven_days_ago = current_time - timedelta(days=7)
    
    # 7일 이상 지난 pending 초대는 완전 삭제
    # 타임존 안전한 비교를 위해 별도 처리
    all_pending_invitations = db.query(ProjectInvitation).filter(
        ProjectInvitation.project_id == project_id,
        ProjectInvitation.status == "pending"
    ).all()
    
    expired_invitations = []
    for inv in all_pending_invitations:
        if inv.invited_at:
            invited_at = inv.invited_at
            if invited_at.tzinfo is None:
                invited_at = invited_at.replace(tzinfo=timezone.utc)
            if invited_at < seven_days_ago:
                expired_invitations.append(inv)
    
    for expired_inv in expired_invitations:
        db.delete(expired_inv)
    
    if expired_invitations:
        db.commit()
    
    # 초대 목록 조회
    invitations = db.query(ProjectInvitation, User).outerjoin(
        User, ProjectInvitation.invited_by == User.user_id
    ).filter(ProjectInvitation.project_id == project_id).all()
    
    invitation_list = []
    for invitation, inviter in invitations:
        # 만료 예정일 계산 (7일 후)
        expires_at = None
        if invitation.invited_at:
            from datetime import timedelta
            # 타임존 처리
            invited_at = invitation.invited_at
            if invited_at.tzinfo is None:
                invited_at = invited_at.replace(tzinfo=timezone.utc)
            expires_at = invited_at + timedelta(days=7)
        
        invitation_list.append({
            "invitation_id": invitation.project_inv_id,
            "email": invitation.email,
            "status": invitation.status,
            "role": invitation.role,
            "invited_by": inviter.name if inviter else "Unknown",
            "invited_at": invitation.invited_at.isoformat() if invitation.invited_at else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "accepted_at": invitation.accepted_at.isoformat() if invitation.accepted_at else None
        })
    
    return {"invitations": invitation_list}

@router.get("/{project_id}/members")
async def get_project_members(
    project_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """프로젝트 멤버 목록 조회"""
    # 프로젝트 존재 확인
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    
    # 프로젝트 멤버인지 확인
    is_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if not is_member:
        raise HTTPException(status_code=403, detail="프로젝트 멤버만 접근할 수 있습니다")
    
    # 멤버 목록 조회
    members = db.query(ProjectMember, User).join(
        User, ProjectMember.user_id == User.user_id
    ).filter(ProjectMember.project_id == project_id).all()
    
    member_list = []
    for member, user in members:
        member_list.append({
            "user_id": user.user_id,
            "email": user.email,
            "name": user.name,
            "role": member.role
        })
    
    return {"members": member_list}

@router.delete("/{project_id}/members/{user_id}")
async def remove_project_member(
    project_id: int,
    user_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """프로젝트 멤버 제거"""
    # 🔒 프로젝트 소유자 또는 관리자 권한 확인
    current_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if not current_member or current_member.role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="권한이 없습니다")
    
    # 제거할 멤버 조회
    target_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id
    ).first()
    
    if not target_member:
        raise HTTPException(status_code=404, detail="멤버를 찾을 수 없습니다")
    
    # 🔒 프로젝트 소유자는 제거할 수 없음
    if target_member.role == "owner":
        raise HTTPException(status_code=400, detail="프로젝트 소유자는 제거할 수 없습니다")
    
    # 🔒 관리자는 다른 관리자를 제거할 수 없음 (소유자만 가능)
    if current_member.role == "admin" and target_member.role == "admin":
        raise HTTPException(status_code=403, detail="관리자는 다른 관리자를 제거할 수 없습니다")
    
    # 🔒 마지막 관리자/소유자 제거 방지
    if user_id == current_user.user_id:
        # 남은 관리자/소유자 수 확인
        admin_count = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.role.in_(["owner", "admin"]),
            ProjectMember.user_id != user_id
        ).count()
        
        if admin_count == 0:
            raise HTTPException(status_code=400, detail="마지막 관리자는 제거할 수 없습니다")
    
    db.delete(target_member)
    db.commit()
    
    return {"message": "멤버가 성공적으로 제거되었습니다"}

@router.put("/{project_id}/members/{user_id}/role")
async def update_member_role(
    project_id: int,
    user_id: int,
    role_data: dict,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """프로젝트 멤버 권한 변경"""
    new_role = role_data.get("role")
    
    if new_role not in ["viewer", "member", "admin", "owner"]:
        raise HTTPException(status_code=400, detail="유효하지 않은 권한입니다")
    
    # 현재 사용자 권한 확인 - 🔒 소유자/관리자만 권한 변경 가능
    current_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if not current_member or current_member.role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="관리자 이상 권한이 필요합니다")
    
    # 변경할 멤버 조회
    target_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id
    ).first()
    
    if not target_member:
        raise HTTPException(status_code=404, detail="멤버를 찾을 수 없습니다")
    
    # 🔒 소유자/관리자는 권한 변경 불가 (멤버/뷰어만 가능)
    if target_member.role in ["owner", "admin"]:
        raise HTTPException(status_code=400, detail="소유자와 관리자의 권한은 변경할 수 없습니다")
    
    # 🔒 관리자는 admin/owner 권한 부여 불가
    if current_member.role == "admin" and new_role in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="소유자만 관리자 이상 권한을 부여할 수 있습니다")
    
    # 🔒 소유자 권한 이전 처리 (소유자만 가능)
    if new_role == "owner":
        if current_member.role != "owner":
            raise HTTPException(status_code=403, detail="소유자만 소유권을 이전할 수 있습니다")
        
        if target_member.role == "owner":
            raise HTTPException(status_code=400, detail="이미 소유자입니다")
        
        # 소유권 이전: 새 소유자로 변경, 기존 소유자는 관리자로
        current_member.role = "admin"
        target_member.role = "owner"
    elif new_role == "admin":
        # 🔒 관리자 권한 부여는 소유자만 가능
        if current_member.role != "owner":
            raise HTTPException(status_code=403, detail="소유자만 관리자 권한을 부여할 수 있습니다")
        
        target_member.role = "admin"
    else:
        # 멤버/뷰어 권한으로 변경
        target_member.role = new_role
    
    db.commit()
    
    return {"message": f"권한이 {new_role}로 변경되었습니다"}

@router.delete("/invitations/{invitation_id}")
async def cancel_invitation(
    invitation_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """초대 취소"""
    invitation = db.query(ProjectInvitation).filter(
        ProjectInvitation.project_inv_id == invitation_id
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="초대장을 찾을 수 없습니다")
    
    # 초대한 사람이거나 프로젝트 소유자만 취소 가능
    project_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == invitation.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if invitation.invited_by != current_user.user_id and (not project_member or project_member.role not in ["owner", "admin"]):
        raise HTTPException(status_code=403, detail="권한이 없습니다")
    
    db.delete(invitation)
    db.commit()
    
    return {"message": "초대가 취소되었습니다"}

@router.post("/invitations/{invitation_id}/resend")
async def resend_invitation(
    invitation_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """초대 재전송"""
    invitation = db.query(ProjectInvitation).filter(
        ProjectInvitation.project_inv_id == invitation_id,
        ProjectInvitation.status == "pending"
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="유효한 초대장을 찾을 수 없습니다")
    
    # 초대한 사람이거나 프로젝트 소유자만 재전송 가능
    project_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == invitation.project_id,
        ProjectMember.user_id == current_user.user_id
    ).first()
    
    if invitation.invited_by != current_user.user_id and (not project_member or project_member.role not in ["owner", "admin"]):
        raise HTTPException(status_code=403, detail="권한이 없습니다")
    
    # 프로젝트 정보 조회
    project = db.query(Project).filter(Project.project_id == invitation.project_id).first()
    
    # 이메일 재전송 (백그라운드 작업)
    background_tasks.add_task(
        send_invitation_email,
        invitation.email,
        project.title,
        current_user.name,
        invitation.project_inv_id
    )
    
    return {"message": "초대장이 재전송되었습니다"}

@router.get("/user/workspaces")
async def get_user_workspaces(
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """사용자의 워크스페이스 목록 조회 (초대 수락용)"""
    workspaces = db.query(Workspace).filter(
        Workspace.user_id == current_user.user_id
    ).order_by(Workspace.order.asc()).all()
    
    workspace_list = []
    for workspace in workspaces:
        workspace_list.append({
            "workspace_id": workspace.workspace_id,
            "name": workspace.name,
            "order": workspace.order
        })
    
    return {"workspaces": workspace_list}

class CreateWorkspaceRequest(BaseModel):
    name: str

@router.post("/user/workspaces")
async def create_user_workspace(
    request: CreateWorkspaceRequest,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """워크스페이스 생성 (초대 수락용)"""
    # 사용자의 가장 큰 order 찾기
    max_order = db.query(Workspace.order).filter(
        Workspace.user_id == current_user.user_id
    ).order_by(Workspace.order.desc()).first()
    
    next_order = (max_order[0] + 1) if max_order else 0
    
    # 새 워크스페이스 생성
    new_workspace = Workspace(
        name=request.name,
        user_id=current_user.user_id,
        order=next_order
    )
    
    db.add(new_workspace)
    db.commit()
    db.refresh(new_workspace)
    
    return {
        "workspace_id": new_workspace.workspace_id,
        "name": new_workspace.name,
        "order": new_workspace.order
    }

@router.post("/invitations/{invitation_id}/reject")
async def reject_invitation(
    invitation_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """초대 거절"""
    # 1. 초대장 확인
    invitation = db.query(ProjectInvitation).filter(
        ProjectInvitation.project_inv_id == invitation_id,
        ProjectInvitation.status == "pending"
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="유효하지 않은 초대장입니다")
    
    # 2. 이메일 일치 확인
    if current_user.email != invitation.email:
        raise HTTPException(status_code=403, detail="초대 대상자만 거절할 수 있습니다")
    
    # 3. 초대장 상태 업데이트
    invitation.status = "rejected"
    invitation.accepted_at = datetime.now(timezone.utc)  # 처리 시간 기록 (수락/거절 공통)
    
    db.commit()
    return {"message": "초대를 거절했습니다"}

