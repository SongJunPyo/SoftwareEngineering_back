from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from backend.models.user import User
from backend.database.base import get_db
from backend.middleware.auth import verify_token
import bcrypt

router = APIRouter(prefix="/api/v1/user", tags=["UserPassword"])

@router.patch("/password", status_code=204)
def change_password(
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    confirm_password = data.get("confirm_password")

    if not current_password or not new_password or not confirm_password:
        raise HTTPException(status_code=400, detail="모든 비밀번호를 입력하세요.")

    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="새 비밀번호가 일치하지 않습니다.")

    # 현재 비밀번호 확인
    if not bcrypt.checkpw(current_password.encode("utf-8"), current_user.password.encode("utf-8")):
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")

    # 새 비밀번호 해싱 및 저장
    hashed_pw = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    current_user.password = hashed_pw
    db.commit()
    return 