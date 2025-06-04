from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
import os
from datetime import datetime
from backend.database.base import get_db
from backend.middleware.auth import get_current_user
from backend.models import ProjectInvitation, ProjectMember, User
from backend.models import Project  # 추가해야 함

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

@router.post("/{project_id}/invite")


async def invite_user(
    project_id: int,
    invite_data: InviteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # 프로젝트 권한 확인
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    
    # 이미 멤버인지 확인
    existing_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.email == invite_data.email

    ).first()
    
    if existing_member:
        raise HTTPException(status_code=400, detail="이미 프로젝트 멤버입니다")
    
    # 초대 생성
    invitation = ProjectInvitation(
        project_id=project_id,
        email=invite_data.email,
        invited_by=current_user.user_id,
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

async def send_invitation_email(email: str, project_name: str, inviter_name: str, invitation_id: str):
    """실제 이메일 전송 함수"""
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #333;">프로젝트 초대장</h2>
                <p>안녕하세요!</p>
                <p><strong>{inviter_name}</strong>님이 <strong>"{project_name}"</strong> 프로젝트에 초대했습니다.</p>
                <div style="margin: 30px 0;">
                    <a href="https://yourapp.com/invite/{invitation_id}" 
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

@router.post("/invitations/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. 초대장 확인
    invitation = db.query(ProjectInvitation).filter(
        ProjectInvitation.id == invitation_id,
        ProjectInvitation.status == "pending"
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="유효하지 않은 초대장입니다")
    
    # 2. 이메일 일치 확인
    if current_user.email != invitation.email:
        raise HTTPException(status_code=403, detail="초대 대상자만 수락할 수 있습니다")
    
    # 3. 멤버 추가
    new_member = ProjectMember(
        project_id=invitation.project_id,
        user_id=current_user.user_id,
        email=current_user.email,
        role="member"
    )
    db.add(new_member)
    
    # 4. 초대장 상태 업데이트
    invitation.status = "accepted"
    invitation.accepted_at = datetime.utcnow()
    
    db.commit()
    return {"message": "프로젝트에 성공적으로 참여했습니다"}

