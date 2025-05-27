from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.base import get_db
from backend.schemas.LojginSignUP import LoginRequest
from backend.models.user import User
import bcrypt

router = APIRouter(prefix="/api/v1")

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    # 사용자 조회
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자입니다."
        )

    # 비밀번호 확인
    if not bcrypt.checkpw(request.password.encode("utf-8"), user.password.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 일치하지 않습니다."
        )

    # 로그인 성공
    return {"message": "로그인 성공", "user_id": user.user_id, "email": user.email}
