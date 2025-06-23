from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.models.user import User
from backend.models.workspace import Workspace
from backend.database.base import get_db
from backend.utils.jwt_utils import create_access_token, create_refresh_token
from backend.config.settings import KAKAO_CLIENT_ID, KAKAO_REDIRECT_URI, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
import bcrypt
import requests
import re
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/oauth", tags=["OAuth"])

@router.post("/kakao")
def kakao_oauth(data: dict, db: Session = Depends(get_db)):
    """카카오 OAuth 로그인"""
    logger.info(f"카카오 OAuth 요청 받음: {data}")
    
    code = data.get("code")
    if not code:
        logger.error("카카오 인증 코드가 없습니다.")
        raise HTTPException(status_code=400, detail="카카오 인증 코드가 없습니다.")

    try:
        logger.info(f"카카오 설정 - CLIENT_ID: {KAKAO_CLIENT_ID}, REDIRECT_URI: {KAKAO_REDIRECT_URI}")
        
        # 1. 카카오 토큰 요청
        token_url = "https://kauth.kakao.com/oauth/token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": KAKAO_CLIENT_ID,
            "redirect_uri": KAKAO_REDIRECT_URI,
            "code": code,
        }
        logger.info(f"카카오 토큰 요청: {token_url}")
        logger.info(f"토큰 요청 데이터: {token_data}")
        
        token_res = requests.post(token_url, data=token_data)
        logger.info(f"카카오 토큰 응답 상태: {token_res.status_code}")
        logger.info(f"카카오 토큰 응답: {token_res.text}")
        
        if token_res.status_code != 200:
            logger.error(f"카카오 토큰 요청 실패: {token_res.status_code} - {token_res.text}")
            raise HTTPException(status_code=400, detail="카카오 토큰 요청 실패")
        
        token_info = token_res.json()
        access_token = token_info.get("access_token")
        if not access_token:
            logger.error("카카오 액세스 토큰을 받지 못했습니다.")
            raise HTTPException(status_code=400, detail="카카오 액세스 토큰을 받지 못했습니다.")

        # 2. 토큰 유효성 검증 (사용자 정보 요청으로 검증)
        user_url = "https://kapi.kakao.com/v2/user/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        logger.info(f"카카오 사용자 정보 요청: {user_url}")
        
        user_res = requests.get(user_url, headers=headers)
        logger.info(f"카카오 사용자 정보 응답 상태: {user_res.status_code}")
        logger.info(f"카카오 사용자 정보 응답: {user_res.text}")
        
        if user_res.status_code != 200:
            logger.error(f"카카오 사용자 정보 요청 실패: {user_res.status_code} - {user_res.text}")
            if user_res.status_code == 401:
                raise HTTPException(status_code=401, detail="유효하지 않은 카카오 토큰입니다.")
            else:
                raise HTTPException(status_code=400, detail="카카오 사용자 정보 요청 실패")
        
        kakao_info = user_res.json()
        kakao_email = kakao_info.get("kakao_account", {}).get("email")
        kakao_name = kakao_info.get("properties", {}).get("nickname", "카카오사용자")

        logger.info(f"카카오 사용자 정보 - 이메일: {kakao_email}, 이름: {kakao_name}")

        if not kakao_email:
            logger.error("카카오 계정에 이메일이 없습니다.")
            raise HTTPException(status_code=400, detail="카카오 계정에 이메일이 없습니다.")

        # 3. 기존 사용자 확인
        user = db.query(User).filter(User.email == kakao_email).first()
        if user:
            logger.info(f"기존 사용자 발견: {user.email}")
            
            # 기존 사용자의 provider가 다르면 에러 (구글과 동일한 정책)
            if getattr(user, "provider", "local") != "kakao":
                logger.error(f"이미 다른 방법으로 가입된 이메일입니다. (현재 provider: {user.provider})")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 다른 방법으로 가입된 이메일입니다."
                )
            
            # JWT 토큰 생성
            token_data = {"sub": str(user.user_id), "email": user.email}
            access_token = create_access_token(token_data)
            refresh_token = create_refresh_token(token_data)
            
            logger.info(f"카카오 로그인 성공 - 기존 사용자: {user.email}")
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name
            }
        else:
            logger.info(f"신규 사용자 - 추가 정보 필요: {kakao_email}")
            # 신규 회원: 추가 정보 필요 응답 (구글과 동일한 방식)
            return {
                "extra_info_required": True,
                "email": kakao_email,
                "provider": "kakao"
            }
    
    except requests.RequestException as e:
        logger.error(f"카카오 API 요청 중 오류: {e}")
        raise HTTPException(status_code=500, detail="카카오 API 요청 중 오류가 발생했습니다.")
    except Exception as e:
        logger.error(f"카카오 로그인 처리 중 오류: {e}")
        raise HTTPException(status_code=500, detail="카카오 로그인 처리 중 오류가 발생했습니다.")

@router.post("/kakao/register")
def kakao_register(data: dict, db: Session = Depends(get_db)):
    """카카오 OAuth 회원가입 (추가 정보 입력 후)"""
    logger.info(f"카카오 회원가입 요청 받음: {data}")
    
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
    
    try:
        # 비밀번호 해싱
        import bcrypt
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        # 새 사용자 생성
        new_user = User(
            email=email,
            password=hashed_pw,
            name=name,
            provider="kakao"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # 기본 워크스페이스 생성 (order=1)
        default_workspace = Workspace(
            user_id=new_user.user_id,
            name="기본 워크스페이스",
            order=1
        )
        
        db.add(default_workspace)
        db.commit()
        
        # JWT 토큰 생성
        token_data = {"sub": str(new_user.user_id), "email": new_user.email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        logger.info(f"카카오 회원가입 성공: {new_user.email}")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": new_user.user_id,
            "email": new_user.email,
            "name": new_user.name
        }
        
    except Exception as e:
        logger.error(f"카카오 회원가입 처리 중 오류: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="카카오 회원가입 처리 중 오류가 발생했습니다.")

@router.post("/naver")
def naver_oauth(data: dict, db: Session = Depends(get_db)):
    """네이버 OAuth 로그인"""
    logger.info(f"네이버 OAuth 요청 받음: {data}")
    
    code = data.get("code")
    state = data.get("state")
    if not code:
        logger.error("네이버 인증 코드가 없습니다.")
        raise HTTPException(status_code=400, detail="네이버 인증 코드가 없습니다.")

    try:
        logger.info(f"네이버 설정 - CLIENT_ID: {NAVER_CLIENT_ID}, CLIENT_SECRET: {NAVER_CLIENT_SECRET}")
        
        # 1. 네이버 토큰 요청
        token_url = "https://nid.naver.com/oauth2.0/token"
        token_params = {
            "grant_type": "authorization_code",
            "client_id": NAVER_CLIENT_ID,
            "client_secret": NAVER_CLIENT_SECRET,
            "code": code,
            "state": state,
        }
        logger.info(f"네이버 토큰 요청: {token_url}")
        logger.info(f"토큰 요청 파라미터: {token_params}")
        
        token_res = requests.post(token_url, params=token_params)
        logger.info(f"네이버 토큰 응답 상태: {token_res.status_code}")
        logger.info(f"네이버 토큰 응답: {token_res.text}")
        
        if token_res.status_code != 200:
            logger.error(f"네이버 토큰 요청 실패: {token_res.status_code} - {token_res.text}")
            raise HTTPException(status_code=400, detail="네이버 토큰 요청 실패")
        
        token_info = token_res.json()
        access_token = token_info.get("access_token")
        if not access_token:
            logger.error("네이버 access_token 없음")
            raise HTTPException(status_code=400, detail="네이버 access_token 없음")

        # 2. 토큰 유효성 검증 (사용자 정보 요청으로 검증)
        user_url = "https://openapi.naver.com/v1/nid/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        logger.info(f"네이버 사용자 정보 요청: {user_url}")
        
        user_res = requests.get(user_url, headers=headers)
        logger.info(f"네이버 사용자 정보 응답 상태: {user_res.status_code}")
        logger.info(f"네이버 사용자 정보 응답: {user_res.text}")
        
        if user_res.status_code != 200:
            logger.error(f"네이버 사용자 정보 요청 실패: {user_res.status_code} - {user_res.text}")
            if user_res.status_code == 401:
                raise HTTPException(status_code=401, detail="유효하지 않은 네이버 토큰입니다.")
            else:
                raise HTTPException(status_code=400, detail="네이버 사용자 정보 요청 실패")
        
        naver_info = user_res.json().get("response", {})
        naver_email = naver_info.get("email")
        naver_name = naver_info.get("name", "네이버사용자")

        logger.info(f"네이버 사용자 정보 - 이메일: {naver_email}, 이름: {naver_name}")

        if not naver_email:
            logger.error("네이버 계정에 이메일이 없습니다.")
            raise HTTPException(status_code=400, detail="네이버 계정에 이메일이 없습니다.")

        # 3. 기존 사용자 확인
        user = db.query(User).filter(User.email == naver_email).first()
        if user:
            logger.info(f"기존 사용자 발견: {user.email}")
            
            # 기존 사용자의 provider가 다르면 에러 (구글과 동일한 정책)
            if getattr(user, "provider", "local") != "naver":
                logger.error(f"이미 다른 방법으로 가입된 이메일입니다. (현재 provider: {user.provider})")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 다른 방법으로 가입된 이메일입니다."
                )
            
            # JWT 토큰 생성
            token_data = {"sub": str(user.user_id), "email": user.email}
            access_token = create_access_token(token_data)
            refresh_token = create_refresh_token(token_data)
            
            logger.info(f"네이버 로그인 성공 - 기존 사용자: {user.email}")
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name
            }
        else:
            logger.info(f"신규 사용자 - 추가 정보 필요: {naver_email}")
            # 신규 회원: 추가 정보 필요 응답 (구글과 동일한 방식)
            return {
                "extra_info_required": True,
                "email": naver_email,
                "provider": "naver"
            }
    
    except requests.RequestException as e:
        logger.error(f"네이버 API 요청 중 오류: {e}")
        raise HTTPException(status_code=500, detail="네이버 API 요청 중 오류가 발생했습니다.")
    except Exception as e:
        logger.error(f"네이버 로그인 처리 중 오류: {e}")
        raise HTTPException(status_code=500, detail="네이버 로그인 처리 중 오류가 발생했습니다.")

@router.post("/naver/register")
def naver_register(data: dict, db: Session = Depends(get_db)):
    """네이버 OAuth 회원가입 (추가 정보 입력 후)"""
    logger.info(f"네이버 회원가입 요청 받음: {data}")
    
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
    
    try:
        # 비밀번호 해싱
        import bcrypt
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        # 새 사용자 생성
        new_user = User(
            email=email,
            password=hashed_pw,
            name=name,
            provider="naver"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # 기본 워크스페이스 생성 (order=1)
        default_workspace = Workspace(
            user_id=new_user.user_id,
            name="기본 워크스페이스",
            order=1
        )
        
        db.add(default_workspace)
        db.commit()
        
        # JWT 토큰 생성
        token_data = {"sub": str(new_user.user_id), "email": new_user.email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        logger.info(f"네이버 회원가입 성공: {new_user.email}")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": new_user.user_id,
            "email": new_user.email,
            "name": new_user.name
        }
        
    except Exception as e:
        logger.error(f"네이버 회원가입 처리 중 오류: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="네이버 회원가입 처리 중 오류가 발생했습니다.")

@router.post("/google")
def google_oauth(data: dict, db: Session = Depends(get_db)):
    """구글 OAuth 로그인"""
    access_token = data.get("access_token")
    email = data.get("email")
    name = data.get("name")

    if not all([access_token, email, name]):
        raise HTTPException(status_code=400, detail="필수 정보가 누락되었습니다.")

    try:
        # 구글 토큰 검증
        response = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="유효하지 않은 구글 토큰입니다.")
        
        google_user_info = response.json()
        if google_user_info.get("email") != email:
            raise HTTPException(status_code=401, detail="이메일이 일치하지 않습니다.")

        # 사용자 조회 또는 생성
        user = db.query(User).filter(User.email == email).first()
        if user:
            # 기존 사용자의 provider가 다르면 에러
            if getattr(user, "provider", "local") != "google":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 다른 방법으로 가입된 이메일입니다."
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
        else:
            # 신규 회원: 추가 정보 필요 응답
            return {
                "extra_info_required": True,
                "email": email,
                "provider": "google"
            }
    
    except requests.RequestException:
        raise HTTPException(status_code=500, detail="구글 API 요청 중 오류가 발생했습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail="구글 로그인 처리 중 오류가 발생했습니다.")

@router.post("/google/register")
def google_register(data: dict, db: Session = Depends(get_db)):
    """구글 OAuth 회원가입 (추가 정보 입력 후)"""
    logger.info(f"구글 회원가입 요청 받음: {data}")
    
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
    
    try:
        # 비밀번호 해싱
        import bcrypt
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
        
        # 기본 워크스페이스 생성 (order=1)
        default_workspace = Workspace(
            user_id=new_user.user_id,
            name="기본 워크스페이스",
            order=1
        )
        
        db.add(default_workspace)
        db.commit()
        
        # JWT 토큰 생성
        token_data = {"sub": str(new_user.user_id), "email": new_user.email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        logger.info(f"구글 회원가입 성공: {new_user.email}")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": new_user.user_id,
            "email": new_user.email,
            "name": new_user.name
        }
        
    except Exception as e:
        logger.error(f"구글 회원가입 처리 중 오류: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="구글 회원가입 처리 중 오류가 발생했습니다.")

