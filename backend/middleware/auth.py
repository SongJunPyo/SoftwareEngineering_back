from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from backend.database.base import get_db
from sqlalchemy.orm import Session
from backend.models.user import User
from backend.utils.jwt_utils import verify_token as jwt_verify_token

security = HTTPBearer()

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    db: Session = Depends(get_db)
) -> User:
    """JWT 토큰 검증 및 사용자 반환"""
    try:
        token = credentials.credentials
        payload = jwt_verify_token(token)
        
        # 액세스 토큰인지 확인
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 토큰 타입입니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 사용자 존재 확인
        user = db.query(User).filter(User.user_id == int(payload['sub'])).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="존재하지 않는 사용자입니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증에 실패했습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def verify_refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """리프레시 토큰 검증 및 사용자 반환"""
    try:
        token = credentials.credentials
        payload = jwt_verify_token(token)
        
        # 리프레시 토큰인지 확인
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 리프레시 토큰입니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 사용자 존재 확인
        user = db.query(User).filter(User.user_id == int(payload['sub'])).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="존재하지 않는 사용자입니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰이 만료되었습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 리프레시 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 검증에 실패했습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        ) 