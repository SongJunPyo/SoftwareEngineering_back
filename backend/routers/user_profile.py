from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.models.user import User
from backend.database.base import get_db
from backend.middleware.auth import verify_token

router = APIRouter(prefix="/api/v1/user", tags=["UserProfile"])

@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "name": current_user.name,
        "provider": current_user.provider
    } 