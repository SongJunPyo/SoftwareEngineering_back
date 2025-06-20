from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from backend.models.user_setting import UserSetting
from backend.models.user import User
from backend.database.base import get_db
from backend.middleware.auth import verify_token
from typing import Dict, Any

router = APIRouter(prefix="/api/v1/user-settings", tags=["User Settings"])

@router.get("/")
def get_user_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """사용자 설정 조회"""
    user_setting = db.query(UserSetting).filter(
        UserSetting.user_id == current_user.user_id
    ).first()
    
    if not user_setting:
        # 설정이 없으면 기본값으로 생성
        user_setting = UserSetting(
            user_id=current_user.user_id,
            email=current_user.email,
            nickname=current_user.name,
            bio=None,
            img_path=None
        )
        db.add(user_setting)
        db.commit()
        db.refresh(user_setting)
    
    return {
        "user_id": user_setting.user_id,
        "email": user_setting.email,
        "nickname": user_setting.nickname,
        "bio": user_setting.bio,
        "img_path": user_setting.img_path
    }

@router.put("/")
def update_user_settings(
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """사용자 설정 업데이트"""
    user_setting = db.query(UserSetting).filter(
        UserSetting.user_id == current_user.user_id
    ).first()
    
    if not user_setting:
        # 설정이 없으면 새로 생성
        user_setting = UserSetting(
            user_id=current_user.user_id,
            email=current_user.email,
            nickname=current_user.name,
            bio=None,
            img_path=None
        )
        db.add(user_setting)
    
    # 필드 업데이트
    email = data.get("email")
    nickname = data.get("nickname")
    bio = data.get("bio")
    img_path = data.get("img_path")
    
    if email is not None:
        user_setting.email = email
    
    if nickname is not None:
        user_setting.nickname = nickname
    
    if bio is not None:
        user_setting.bio = bio
    
    if img_path is not None:
        user_setting.img_path = img_path
    
    db.commit()
    db.refresh(user_setting)
    
    return {
        "user_id": user_setting.user_id,
        "email": user_setting.email,
        "nickname": user_setting.nickname,
        "bio": user_setting.bio,
        "img_path": user_setting.img_path
    }

@router.delete("/")
def reset_user_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """사용자 설정 초기화"""
    user_setting = db.query(UserSetting).filter(
        UserSetting.user_id == current_user.user_id
    ).first()
    
    if user_setting:
        # 기본값으로 리셋
        user_setting.email = current_user.email
        user_setting.nickname = current_user.name
        user_setting.bio = None
        user_setting.img_path = None
        
        db.commit()
        db.refresh(user_setting)
    
    return {"message": "사용자 설정이 초기화되었습니다."}