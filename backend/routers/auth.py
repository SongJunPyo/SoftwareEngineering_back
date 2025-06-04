from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.schemas.LojginSignUP import RegisterRequest, LoginRequest
from backend.models.user import User
from backend.database.base import get_db
from backend.utils.jwt_utils import create_access_token, create_refresh_token, refresh_access_token
from backend.middleware.auth import verify_refresh_token
import bcrypt

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(register_data: RegisterRequest, db: Session = Depends(get_db)):
    """일반 회원가입"""
    # 이메일 중복 확인
    existing_user = db.query(User).filter(User.email == register_data.email).first()
    if existing_user:
        if existing_user.provider == "google":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="구글계정으로 연동되어있는 이메일입니다."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 존재하는 이메일입니다."
            )

    # 비밀번호 해싱
    hashed_pw = bcrypt.hashpw(
        register_data.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # 사용자 생성
    new_user = User(
        email=register_data.email,
        password=hashed_pw,
        name=register_data.name,
        provider="local"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "회원가입 성공", 
        "user_id": new_user.user_id,
        "email": new_user.email,
        "name": new_user.name
    }

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """로그인"""
    # 사용자 조회
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자입니다."
        )

    # OAuth 사용자 체크 (비밀번호 검증 전에)
    if user.provider != "local":
        if user.provider == "google":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="구글 로그인을 사용해주세요."
            )
        elif user.provider == "kakao":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="카카오 로그인을 사용해주세요."
            )
        elif user.provider == "naver":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="네이버 로그인을 사용해주세요."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"{user.provider} 로그인을 사용해주세요."
            )

    # 비밀번호 검증 (일반 사용자만)
    try:
        # 저장된 비밀번호가 비어있거나 None인 경우 체크
        if not user.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="비밀번호가 설정되지 않은 계정입니다. OAuth 로그인을 사용해주세요."
            )
        
        # bcrypt 비밀번호 검증
        if not bcrypt.checkpw(request.password.encode("utf-8"), user.password.encode("utf-8")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="비밀번호가 일치하지 않습니다."
            )
    except ValueError as e:
        # bcrypt 검증 중 에러 (잘못된 해시 형식 등)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="비밀번호 검증 중 오류가 발생했습니다."
        )
    except Exception as e:
        # 기타 예외
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그인 처리 중 오류가 발생했습니다."
        )

    # JWT 토큰 생성
    token_data = {"sub": str(user.user_id), "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name
    }

@router.post("/refresh")
def refresh_token(current_user: User = Depends(verify_refresh_token)):
    """리프레시 토큰으로 새로운 액세스 토큰 발급"""
    token_data = {"sub": str(current_user.user_id), "email": current_user.email}
    new_access_token = create_access_token(token_data)
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }

@router.post("/check-email")
def check_email(data: dict, db: Session = Depends(get_db)):
    """이메일 중복 확인"""
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="이메일을 입력해주세요.")
    
    exists = db.query(User).filter(User.email == email).first() is not None
    return {"exists": exists} 