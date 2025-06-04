"""
DEPRECATED: 이 파일은 더 이상 사용되지 않습니다.
새로운 기능별로 분리된 라우터들을 사용해주세요.
"""

# 기존 코드는 주석 처리됨
# from fastapi import APIRouter, Depends, HTTPException, status
# from schemas.LojginSignUP import AccountCreate, LoginRequest
# from sqlalchemy import select
# from sqlalchemy.orm import Session
# from database.base import get_db
# from models.user import User
# import bcrypt

# router = APIRouter(prefix="/api/v1")

# # Pydantic 모델 수정

# @router.post(
#     "/register",
#     status_code=status.HTTP_201_CREATED,
#     responses={
#         201: {"description": "account created successfully"},
#         400: {"description": "Email already registered"},
#         500: {"description": "zz Internal server error"}
#     }
# )
# async def register_account(
#     account_data: AccountCreate,
#     db: Session = Depends(get_db)
# ):
#     try:
#         existing_user = db.scalar(
#             select(User).where(User.email == account_data.email)
#         )
#         if existing_user:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="이미 등록된 이메일 주소입니다."
#             )

#         hashed_password = bcrypt.hashpw(
#             account_data.password.encode('utf-8'),
#             bcrypt.gensalt(rounds=12)
#         ).decode('utf-8')

#         new_user = User(
#             email=account_data.email,
#             password=hashed_password,
#             name=account_data.name,
#             phone_number=account_data.phone_number,
#             address=account_data.address,
#             account_type=account_data.account_type,
#             approved=False
#         )
        
#         db.add(new_user)
#         db.commit()
#         db.refresh(new_user)
        
#         return {
#             "message": "회원가입 성공",
#             "user_id": new_user.user_id
#         }

#     except HTTPException as he:
#         db.rollback()
#         raise he
#     except Exception as e:
#         print(e);
#         # logger.exception(e)       //추천
#         db.rollback()
#         raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")



from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.schemas.LojginSignUP import RegisterRequest
from backend.models.user import User
from backend.database.base import get_db
import bcrypt
import requests

router = APIRouter(prefix="/api/v1")

@router.post("/register", status_code=201)
def register_user(register_data: RegisterRequest, db: Session = Depends(get_db)):
    # 1. 이메일 중복 확인
    existing_user = db.query(User).filter(User.email == register_data.email).first()
    if existing_user:
        if getattr(existing_user, "provider", "local") == "google":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="구글계정으로 연동되어있는 이메일입니다."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 존재하는 이메일입니다."
            )

    # 2. 비밀번호 해싱
    hashed_pw = bcrypt.hashpw(
        register_data.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # 3. 사용자 생성
    new_user = User(
        email=register_data.email,
        password=hashed_pw,
        name=register_data.name,
        provider="local"  # 일반 회원가입은 local
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "회원가입 성공", "user_id": new_user.user_id}

@router.post("/check-email")
def check_email(data: dict, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.email == data["email"]).first() is not None
    return {"exists": exists}

@router.post("/oauth/kakao")
def kakao_oauth(data: dict, db: Session = Depends(get_db)):
    code = data.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="카카오 인증 코드가 없습니다.")

    # 1. 카카오 토큰 요청
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": "4eb3eb8b216e68f32dc551a30aa4bf15",
        "redirect_uri": "http://localhost:3000/oauth/kakao/callback",
        "code": code,
    }
    token_res = requests.post(token_url, data=token_data)
    if token_res.status_code != 200:
        raise HTTPException(status_code=400, detail="카카오 토큰 요청 실패")
    access_token = token_res.json().get("access_token")

    # 2. 사용자 정보 요청
    user_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    user_res = requests.get(user_url, headers=headers)
    if user_res.status_code != 200:
        raise HTTPException(status_code=400, detail="카카오 사용자 정보 요청 실패")
    kakao_info = user_res.json()
    kakao_email = kakao_info.get("kakao_account", {}).get("email")
    kakao_name = kakao_info.get("properties", {}).get("nickname", "카카오사용자")

    if not kakao_email:
        raise HTTPException(status_code=400, detail="카카오 계정에 이메일이 없습니다.")

    user = db.query(User).filter(User.email == kakao_email).first()
    if user:
        if getattr(user, "provider", "local") == "google":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="구글계정으로 연동되어있는 이메일입니다."
            )
        return {"message": "로그인 성공", "user_id": user.user_id, "email": user.email}
    else:
        # 신규 회원: 추가 정보 필요
        return {"extra_info_required": True, "email": kakao_email}

@router.post("/oauth/kakao/register")
def kakao_register(data: dict, db: Session = Depends(get_db)):
    email = data.get("email")
    name = data.get("name")
    password = data.get("password")
    password_confirm = data.get("password_confirm")
    if not all([email, name, password, password_confirm]):
        raise HTTPException(status_code=400, detail="모든 필드를 입력해주세요.")
    if password != password_confirm:
        raise HTTPException(status_code=400, detail="비밀번호가 일치하지 않습니다.")
    import re
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>\[\]\\/~`_\-+=;'']", password):
        raise HTTPException(status_code=422, detail="비밀번호 요구사항이 지켜지지 않았습니다.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="이미 존재하는 이메일입니다.")
    import bcrypt
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    new_user = User(
        email=email,
        password=hashed_pw,
        name=name,
        provider="kakao"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "회원가입 성공", "user_id": new_user.user_id, "email": new_user.email}

@router.post("/oauth/naver")
def naver_oauth(data: dict, db: Session = Depends(get_db)):
    code = data.get("code")
    state = data.get("state")
    if not code:
        raise HTTPException(status_code=400, detail="네이버 인증 코드가 없습니다.")

    # 1. 네이버 토큰 요청
    token_url = "https://nid.naver.com/oauth2.0/token"
    token_params = {
        "grant_type": "authorization_code",
        "client_id": "Z23l4FA17iEUlK9FPEsn",
        "client_secret": "9o1qauKcYd",
        "code": code,
        "state": state,
    }
    token_res = requests.post(token_url, params=token_params)
    if token_res.status_code != 200:
        raise HTTPException(status_code=400, detail="네이버 토큰 요청 실패")
    access_token = token_res.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="네이버 access_token 없음")

    # 2. 사용자 정보 요청
    user_url = "https://openapi.naver.com/v1/nid/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    user_res = requests.get(user_url, headers=headers)
    if user_res.status_code != 200:
        raise HTTPException(status_code=400, detail="네이버 사용자 정보 요청 실패")
    naver_info = user_res.json().get("response", {})
    naver_email = naver_info.get("email")
    naver_name = naver_info.get("name", "네이버사용자")

    if not naver_email:
        raise HTTPException(status_code=400, detail="네이버 계정에 이메일이 없습니다.")

    user = db.query(User).filter(User.email == naver_email).first()
    if user:
        if getattr(user, "provider", "local") == "google":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="구글계정으로 연동되어있는 이메일입니다."
            )
        return {"message": "로그인 성공", "user_id": user.user_id, "email": user.email}
    else:
        # 신규 회원: 추가 정보 필요
        return {"extra_info_required": True, "email": naver_email, "name": naver_name}
