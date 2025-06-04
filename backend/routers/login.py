# ⚠️ 이 파일은 더 이상 사용되지 않습니다.
# 새로운 로그인 기능은 backend/routers/auth.py에서 제공됩니다.
# JWT 토큰 기반 인증이 포함된 완전한 로그인 기능을 사용하려면
# auth.py의 로그인 엔드포인트를 사용해주세요.

"""
DEPRECATED: 이 파일은 더 이상 사용되지 않습니다.
새로운 auth.py 라우터를 사용해주세요.
"""

# 기존 코드는 주석 처리됨
# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.orm import Session
# from backend.database.base import get_db
# from backend.schemas.LojginSignUP import LoginRequest
# from backend.models.user import User
# import bcrypt
# 
# router = APIRouter(prefix="/api/v1")
# 
# @router.post("/login")
# def login(request: LoginRequest, db: Session = Depends(get_db)):
#     # 사용자 조회
#     user = db.query(User).filter(User.email == request.email).first()
# 
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="존재하지 않는 사용자입니다."
#         )
# 
#     # 비밀번호 확인
#     if not bcrypt.checkpw(request.password.encode("utf-8"), user.password.encode("utf-8")):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="비밀번호가 일치하지 않습니다."
#         )
# 
#     # 로그인 성공
#     return {"message": "로그인 성공", "user_id": user.user_id, "email": user.email}
