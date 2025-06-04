import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# JWT 설정
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_super_secret_jwt_key_change_in_production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# OAuth 설정
KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID", "4eb3eb8b216e68f32dc551a30aa4bf15")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://16.176.103.176:8000/oauth/kakao/callback")

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "Z23l4FA17iEUlK9FPEsn")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "9o1qauKcYd")
NAVER_REDIRECT_URI = os.getenv("NAVER_REDIRECT_URI", "http://16.176.103.176:8000/oauth/naver/callback")

# 데이터베이스 설정
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://swe6:4XfmFK3hpNB1XlHBw6cF@sw-engineering.cbwyke862nkz.ap-northeast-2.rds.amazonaws.com:5432/postgres")

# 환경 설정
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # 개발 환경으로 변경
DEBUG = os.getenv("DEBUG", "true").lower() == "true"  # 디버그 모드 활성화

# CORS 설정
ALLOWED_ORIGINS = [
    "http://16.176.103.176:8000",
    "http://16.176.103.176:3000",
    "http://localhost:3000",
    "http://localhost:8000"
]

# 설정 검증
def validate_settings():
    """필수 환경변수 검증"""
    required_vars = [
        "JWT_SECRET_KEY",
        "KAKAO_CLIENT_ID", 
        "NAVER_CLIENT_ID",
        "NAVER_CLIENT_SECRET"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# 개발 환경이 아닌 경우에만 검증
if ENVIRONMENT != "development":
    validate_settings()

# 구글 OAuth는 프론트엔드에서 처리하므로 추가 설정 불필요 