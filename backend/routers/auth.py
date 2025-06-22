from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.schemas.LojginSignUP import RegisterRequest, LoginRequest
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.database.base import get_db
from backend.utils.jwt_utils import create_access_token, create_refresh_token, refresh_access_token
from backend.middleware.auth import verify_refresh_token, verify_token

import bcrypt
import uuid
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# --- 이메일 인증 관련 ---

class VerificationToken(BaseModel):
    token: str

def send_verification_email(recipient_email: str, token: str):
    """인증 이메일을 발송하는 함수"""
    try:
        SMTP_SERVER = os.getenv("SMTP_SERVER")
        SMTP_PORT = int(os.getenv("SMTP_PORT"))
        SMTP_USER = os.getenv("SMTP_USER")
        SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

        # 프론트엔드 인증 페이지 URL
        verification_link = f"http://localhost:3000/verify-email?token={token}"
        
        body = f"""
        <div style="font-family: Arial, sans-serif; text-align: center; padding: 20px;">
            <h2>Planora 회원가입 인증</h2>
            <p>Planora에 가입해주셔서 감사합니다!</p>
            <p>아래 버튼을 클릭하여 이메일 주소 인증을 완료해주세요.</p>
            <a href="{verification_link}"
               style="display: inline-block; padding: 12px 24px; margin: 20px 0; font-size: 16px; color: white; background-color: #f59e0b; text-decoration: none; border-radius: 5px;">
                이메일 인증하기
            </a>
            <p style="font-size: 12px; color: #888;">이 링크는 24시간 동안 유효합니다.</p>
        </div>
        """
        
        msg = MIMEText(body, 'html', 'utf-8')
        msg['Subject'] = "[Planora] 회원가입 이메일 인증을 완료해주세요."
        msg['From'] = SMTP_USER
        msg['To'] = recipient_email
        
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"이메일 발송 중 오류 발생: {e}")
        # 실제 운영 환경에서는 에러 로깅 및 재시도 로직이 필요할 수 있습니다.
        raise HTTPException(status_code=500, detail="인증 이메일 발송에 실패했습니다.")


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(register_data: RegisterRequest, db: Session = Depends(get_db)):
    """일반 회원가입 (이메일 인증 필요)"""
    existing_user = db.query(User).filter(User.email == register_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 가입된 이메일입니다."
        )

    hashed_pw = bcrypt.hashpw(register_data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    verification_token = str(uuid.uuid4())

    new_user = User(
        email=register_data.email,
        password=hashed_pw,
        name=register_data.name,
        provider="local",
        email_verified=False,
        email_verification_token=verification_token,
        email_verification_token_expires_at=datetime.utcnow() + timedelta(hours=24),
        role='pending' # 인증 전 등급
    )
    db.add(new_user)
    db.flush() # user_id를 할당받기 위해 flush

    # 기본 워크스페이스 생성
    default_workspace = Workspace(
        user_id=new_user.user_id,
        name="기본 워크스페이스",
        order=1
    )
    db.add(default_workspace)

    try:
        send_verification_email(new_user.email, verification_token)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"회원가입 중 오류 발생 (이메일 발송 실패): {e}")
        raise HTTPException(status_code=500, detail="회원가입 처리 중 오류가 발생했습니다.")

    return {"message": "회원가입 요청이 완료되었습니다. 이메일을 확인하여 계정을 활성화해주세요."}


@router.post("/verify-email")
def verify_email_and_login(data: VerificationToken, db: Session = Depends(get_db)):
    """이메일 토큰을 검증하고 사용자를 활성화한 뒤, 자동 로그인 처리"""
    token = data.token
    user = db.query(User).filter(User.email_verification_token == token).first()

    if not user:
        # 이미 인증된 사용자가 링크를 다시 클릭했을 가능성을 확인
        verified_user = db.query(User).filter(User.email_verification_token == None, User.email_verified == True).first()
        if verified_user:
             # 토큰이 없어졌지만 이미 인증된 사용자라면, 이메일로 찾아 재로그인 시켜줌
            user_by_email = db.query(User).filter(User.email == verified_user.email).first()
            if user_by_email:
                token_data = {"sub": str(user_by_email.user_id), "email": user_by_email.email}
                access_token = create_access_token(token_data)
                refresh_token = create_refresh_token(token_data)
                return {
                    "message": "이미 인증된 계정입니다. 자동으로 로그인됩니다.",
                    "access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer",
                    "user_id": user_by_email.user_id, "email": user_by_email.email, "name": user_by_email.name, "role": user_by_email.role
                }
        raise HTTPException(status_code=400, detail="유효하지 않은 토큰이거나 이미 사용된 토큰입니다.")

    if user.email_verification_token_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="인증 토큰이 만료되었습니다. 회원가입을 다시 시도해주세요.")

    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_token_expires_at = None
    user.role = "member" # 이메일 인증 시 'member' 등급으로 승격
    db.commit()
    db.refresh(user)

    token_data = {"sub": str(user.user_id), "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "message": "이메일 인증이 완료되었습니다. 자동으로 로그인됩니다.",
        "access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer",
        "user_id": user.user_id, "email": user.email, "name": user.name, "role": user.role
    }


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """로그인"""
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="존재하지 않는 사용자입니다.")
    
    if user.provider != "local":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"{user.provider} 계정으로 로그인해주세요.")

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이메일 인증이 필요합니다. 가입 시 발송된 이메일을 확인해주세요."
        )

    if not user.password or not bcrypt.checkpw(request.password.encode("utf-8"), user.password.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="비밀번호가 일치하지 않습니다.")

    token_data = {"sub": str(user.user_id), "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer",
        "user_id": user.user_id, "email": user.email, "name": user.name, "role": user.role
    }


@router.post("/refresh")
def refresh_token(current_user: User = Depends(verify_refresh_token)):
    """리프레시 토큰으로 새로운 액세스 토큰 발급"""
    token_data = {"sub": str(current_user.user_id), "email": current_user.email}
    new_access_token = create_access_token(token_data)
    
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/check-email")
def check_email(data: dict, db: Session = Depends(get_db)):
    """이메일 중복 확인"""
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="이메일을 입력해주세요.")
    
    exists = db.query(User).filter(User.email == email).first() is not None
    return {"exists": exists}


@router.get("/me")
def get_current_user(current_user: User = Depends(verify_token)):
    """현재 로그인된 사용자 정보 조회"""
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "name": current_user.name,
        "provider": current_user.provider,
        "role": current_user.role,
        "email_notifications_enabled": current_user.email_notifications_enabled,
        "notification_email": current_user.notification_email
    } 