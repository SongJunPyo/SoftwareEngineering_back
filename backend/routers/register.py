from fastapi import APIRouter, Depends, HTTPException, status
from schemas.register import AccountCreate
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.base import get_db
from models.user import User
import bcrypt

router = APIRouter(prefix="/api/v1")

# Pydantic 모델 수정

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "account created successfully"},
        400: {"description": "Email already registered"},
        500: {"description": "zz Internal server error"}
    }
)
async def register_account(
    account_data: AccountCreate,
    db: Session = Depends(get_db)
):
    try:
        existing_user = db.scalar(
            select(User).where(User.email == account_data.email)
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 등록된 이메일 주소입니다."
            )

        hashed_password = bcrypt.hashpw(
            account_data.password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')

        new_user = User(
            email=account_data.email,
            password=hashed_password,
            name=account_data.name,
            phone_number=account_data.phone_number,
            address=account_data.address,
            account_type=account_data.account_type,
            approved=False
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "message": "회원가입 성공",
            "user_id": new_user.user_id
        }

    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        print(e);
        # logger.exception(e)       //추천
        db.rollback()
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")

