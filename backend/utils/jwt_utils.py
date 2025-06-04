import jwt
from datetime import datetime, timedelta
from backend.config.settings import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

def create_access_token(data: dict) -> str:
    """액세스 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """리프레시 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """토큰 검증 및 페이로드 반환"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # 토큰 만료 확인
        if datetime.fromtimestamp(payload['exp']) < datetime.utcnow():
            raise jwt.ExpiredSignatureError("토큰이 만료되었습니다.")
        
        return payload
    except jwt.InvalidTokenError as e:
        raise e

def refresh_access_token(refresh_token: str) -> str:
    """리프레시 토큰으로 새로운 액세스 토큰 생성"""
    try:
        payload = verify_token(refresh_token)
        
        # 리프레시 토큰인지 확인
        if payload.get("type") != "refresh":
            raise jwt.InvalidTokenError("유효하지 않은 리프레시 토큰입니다.")
        
        # 새로운 액세스 토큰 생성
        new_payload = {
            "sub": payload["sub"],
            "email": payload["email"]
        }
        return create_access_token(new_payload)
    except jwt.InvalidTokenError as e:
        raise e 