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
import jwt
from datetime import datetime, timedelta
import os
from backend.models.workspace import Workspace
from backend.models.project import Project
from backend.middleware.auth import verify_token
from fastapi import Body
from backend.models import ProjectMember

router = APIRouter(prefix="/api/v1")

# JWT 설정
JWT_SECRET_KEY = "your_jwt_secret_key_here"  # 실제 운영환경에서는 환경변수로 관리
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

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

@router.post("/oauth/google")
async def google_oauth(data: dict, db: Session = Depends(get_db)):
    access_token = data.get("access_token")
    email = data.get("email")
    name = data.get("name")

    if not all([access_token, email, name]):
        raise HTTPException(status_code=400, detail="필수 정보가 누락되었습니다.")

    # 구글 토큰 검증
    try:
        response = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="유효하지 않은 구글 토큰입니다.")
        
        google_user_info = response.json()
        if google_user_info.get("email") != email:
            raise HTTPException(status_code=401, detail="이메일이 일치하지 않습니다.")
    except Exception as e:
        raise HTTPException(status_code=401, detail="구글 토큰 검증에 실패했습니다.")

    # 사용자 조회 또는 생성
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # 새 사용자 생성
        new_user = User(
            email=email,
            password="",  # 구글 로그인은 비밀번호 없음
            name=name,
            provider="google"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        user = new_user
    elif user.provider != "google":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 일반 회원가입으로 가입된 이메일입니다."
        )

    # JWT 토큰 생성
    access_token = create_access_token({"sub": str(user.user_id), "email": user.email})
    refresh_token = create_refresh_token({"sub": str(user.user_id), "email": user.email})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name
    }

@router.post("/oauth/google/register")
async def google_register(data: dict, db: Session = Depends(get_db)):
    email = data.get("email")
    name = data.get("name")
    password = data.get("password")
    password_confirm = data.get("password_confirm")

    if not all([email, name, password, password_confirm]):
        raise HTTPException(status_code=400, detail="모든 필드를 입력해주세요.")
    if password != password_confirm:
        raise HTTPException(status_code=400, detail="비밀번호가 일치하지 않습니다.")

    # 비밀번호 유효성 검사
    import re
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>\[\]\\/~`_\-+=;'']", password):
        raise HTTPException(status_code=422, detail="비밀번호 요구사항이 지켜지지 않았습니다.")

    # 이메일 중복 확인
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="이미 존재하는 이메일입니다.")

    # 비밀번호 해싱
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # 새 사용자 생성
    new_user = User(
        email=email,
        password=hashed_pw,
        name=name,
        provider="google"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # JWT 토큰 생성
    access_token = create_access_token({"sub": str(new_user.user_id), "email": new_user.email})
    refresh_token = create_refresh_token({"sub": str(new_user.user_id), "email": new_user.email})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": new_user.user_id,
        "email": new_user.email,
        "name": new_user.name
    }

# 워크스페이스(조직) CRUD
@router.post("/workspaces")
def create_workspace(data: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(verify_token)):
    print("조직 생성 - current_user.user_id:", current_user.user_id, "current_user.email:", current_user.email)
    new_ws = Workspace(
        name=data["name"],
        description=data.get("description", ""),
        user_id=current_user.user_id
    )
    db.add(new_ws)
    db.commit()
    db.refresh(new_ws)
    return {"workspace_id": new_ws.workspace_id, "name": new_ws.name, "description": new_ws.description}

@router.get("/workspaces")
def list_workspaces(db: Session = Depends(get_db), current_user: User = Depends(verify_token)):
    workspaces = db.query(Workspace).filter(Workspace.user_id == current_user.user_id).all()
    return [{"workspace_id": ws.workspace_id, "name": ws.name, "description": ws.description} for ws in workspaces]

@router.put("/workspaces/{workspace_id}")
def update_workspace(workspace_id: int, data: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(verify_token)):
    ws = db.query(Workspace).filter(Workspace.workspace_id == workspace_id, Workspace.user_id == current_user.user_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="워크스페이스를 찾을 수 없습니다.")
    ws.name = data.get("name", ws.name)
    ws.description = data.get("description", ws.description)
    db.commit()
    db.refresh(ws)
    return {"workspace_id": ws.workspace_id, "name": ws.name, "description": ws.description}

@router.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int, db: Session = Depends(get_db), current_user: User = Depends(verify_token)):
    ws = db.query(Workspace).filter(Workspace.workspace_id == workspace_id, Workspace.user_id == current_user.user_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="워크스페이스를 찾을 수 없습니다.")
    db.delete(ws)
    db.commit()
    return {"message": "삭제 완료"}

# 프로젝트 CRUD
@router.post("/projects")
def create_project(data: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(verify_token)):
    new_project = Project(
        title=data["title"],
        description=data.get("description", ""),
        workspace_id=data["workspace_id"],
        owner_id=current_user.user_id
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
      # ✅ 자신을 멤버로 등록
    member = ProjectMember(
        project_id=new_project.project_id,
        user_id=current_user.user_id,
        role="owner",
        email=current_user.email  # user 모델에 email 필드가 있다고 가정
    )
    db.add(member)
    db.commit()
    return {
            "project_id": new_project.project_id, 
            "title": new_project.title, 
            "description": new_project.description, 
            "workspace_id": new_project.workspace_id}

@router.get("/projects")
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(verify_token)):
    projects = db.query(Project).filter(Project.owner_id == current_user.user_id).all()
    return [{
        "project_id": p.project_id, 
        "title": p.title, 
        "description": p.description, 
        "workspace_id": p.workspace_id,
        "members": [
                {
                    "user_id": pm.user.user_id,
                    "name": pm.user.name,   # User 모델에 name 필드가 있어야 함
                    "email": pm.user.email,
                    "role": pm.role
                }
                for pm in p.members if pm.user is not None
            ]
        } for p in projects]

@router.put("/projects/{project_id}")
def update_project(project_id: int, data: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(verify_token)):
    project = db.query(Project).filter(Project.project_id == project_id, Project.owner_id == current_user.user_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    project.title = data.get("title", project.title)
    project.description = data.get("description", project.description)
    db.commit()
    db.refresh(project)
    return {"project_id": project.project_id, "title": project.title, "description": project.description, "workspace_id": project.workspace_id}

@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(verify_token)):
    project = db.query(Project).filter(Project.project_id == project_id, Project.owner_id == current_user.user_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    db.delete(project)
    db.commit()
    return {"message": "삭제 완료"}
