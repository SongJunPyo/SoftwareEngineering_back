# 📚 Backend Development Guide

> **Software Engineering Backend API v2.0 개발 가이드**  
> 새로운 기능 개발, 코드 병합, 팀 협업을 위한 종합 가이드

## 📋 목차

- [프로젝트 구조](#프로젝트-구조)
- [개발 환경 설정](#개발-환경-설정)
- [새로운 기능 추가](#새로운-기능-추가)
- [코드 병합 가이드](#코드-병합-가이드)
- [API 문서화](#api-문서화)
- [테스트 가이드](#테스트-가이드)
- [데이터베이스 관리](#데이터베이스-관리)
- [보안 가이드](#보안-가이드)
- [배포 가이드](#배포-가이드)
- [트러블슈팅](#트러블슈팅)

---

## 🏗️ 프로젝트 구조

### 현재 디렉토리 구조
```
backend/
├── config/
│   ├── __init__.py          # 설정 패키지
│   └── settings.py          # 환경 설정 (JWT, OAuth)
├── database/
│   └── base.py              # 데이터베이스 연결 및 세션
├── middleware/
│   ├── __init__.py          # 미들웨어 패키지
│   └── auth.py              # JWT 인증/인가 미들웨어
├── models/
│   ├── __init__.py          # 모델 패키지
│   ├── user.py              # 사용자 모델
│   ├── workspace.py         # 워크스페이스 모델
│   ├── project.py           # 프로젝트 모델
│   ├── task.py              # 태스크 모델
│   ├── tag.py               # 태그 모델
│   ├── comment_file.py      # 댓글/파일 모델
│   └── logs_notification.py # 로그/알림 모델
├── routers/
│   ├── __init__.py          # 라우터 패키지
│   ├── auth.py              # ✅ 일반 회원가입/로그인
│   ├── oauth.py             # ✅ OAuth 로그인 (카카오, 네이버, 구글)
│   ├── workspace.py         # ✅ 워크스페이스 CRUD
│   ├── project.py           # ✅ 프로젝트 CRUD
│   ├── project_order.py     # ✅ 프로젝트 순서 관리
│   ├── register.py          # ❌ DEPRECATED (삭제 예정)
│   └── login.py             # ❌ DEPRECATED (삭제 예정)
├── schemas/
│   └── LojginSignUP.py      # Pydantic 스키마
├── utils/
│   ├── __init__.py          # 유틸리티 패키지
│   └── jwt_utils.py         # JWT 토큰 관리
└── README.md                # 프로젝트 개요
```

### 🎯 아키텍처 원칙

1. **관심사 분리**: 각 모듈은 단일 책임을 가짐
2. **의존성 주입**: FastAPI의 Depends를 활용
3. **계층화 구조**: Router → Service → Model
4. **재사용성**: 공통 로직은 utils 또는 middleware로 분리

---

## ⚙️ 개발 환경 설정

### 1. 필수 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
```bash
# .env 파일 생성 (프로젝트 루트)
cp .env.example .env

# 필수 환경 변수
JWT_SECRET_KEY=your_super_secret_jwt_key_change_in_production
KAKAO_CLIENT_ID=your_kakao_client_id
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
```

### 3. 서버 실행
```bash
# 개발 서버 실행
python main.py

# 또는 uvicorn 직접 실행
uvicorn main:app --host 0.0.0.0 --port 8005 --reload
```

### 4. API 문서 확인
- Swagger UI: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc
- OpenAPI JSON: http://localhost:8005/openapi.json

---

## 🚀 새로운 기능 추가

### 1. 새로운 모델 추가

#### Step 1: 모델 정의
```python
# backend/models/new_model.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.database.base import Base
from datetime import datetime, timezone

class NewModel(Base):
    __tablename__ = "new_models"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # 관계 설정
    user = relationship("User", back_populates="new_models")
```

#### Step 2: 관계 설정 업데이트
```python
# backend/models/user.py에 추가
new_models = relationship("NewModel", back_populates="user")
```

#### Step 3: 모델 등록
```python
# backend/models/__init__.py에 추가
from .new_model import NewModel
```

### 2. 새로운 라우터 추가

#### Step 1: 스키마 정의
```python
# backend/schemas/new_schema.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NewModelCreate(BaseModel):
    name: str
    description: Optional[str] = None

class NewModelResponse(BaseModel):
    id: int
    name: str
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
```

#### Step 2: 라우터 생성
```python
# backend/routers/new_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.models.new_model import NewModel
from backend.schemas.new_schema import NewModelCreate, NewModelResponse
from backend.database.base import get_db
from backend.middleware.auth import verify_token
from backend.models.user import User
from typing import List

router = APIRouter(prefix="/api/v1/new-models", tags=["NewModel"])

@router.post("/", response_model=NewModelResponse, status_code=status.HTTP_201_CREATED)
def create_new_model(
    data: NewModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """새로운 모델 생성"""
    new_model = NewModel(
        name=data.name,
        user_id=current_user.user_id
    )
    
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    
    return new_model

@router.get("/", response_model=List[NewModelResponse])
def list_new_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """새로운 모델 목록 조회"""
    models = db.query(NewModel).filter(
        NewModel.user_id == current_user.user_id
    ).all()
    
    return models
```

#### Step 3: 메인 앱에 라우터 등록
```python
# main.py에 추가
from backend.routers import new_router

app.include_router(new_router.router)  # 새로운 라우터 등록
```

### 3. 새로운 미들웨어 추가

```python
# backend/middleware/new_middleware.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

async def new_middleware(request: Request, call_next):
    """새로운 미들웨어 예시"""
    try:
        # 전처리
        response = await call_next(request)
        # 후처리
        return response
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": "내부 서버 오류"}
        )
```

---

## 🔄 코드 병합 가이드

### 1. Git 브랜치 전략

#### 브랜치 명명 규칙
```bash
feature/기능명           # 새로운 기능 개발
bugfix/버그명           # 버그 수정
hotfix/긴급수정명       # 긴급 수정
refactor/리팩토링명     # 코드 리팩토링
```

#### 예시
```bash
feature/task-management
bugfix/login-error-handling
hotfix/cors-policy-fix
refactor/auth-middleware
```

### 2. 병합 전 체크리스트

#### ✅ 코드 품질 체크
- [ ] 코딩 스타일 일관성 확인
- [ ] 타입 힌트 추가 확인
- [ ] Docstring 작성 확인
- [ ] 불필요한 주석 제거
- [ ] Import 정리

#### ✅ 기능 테스트
- [ ] 새로운 API 엔드포인트 테스트
- [ ] 기존 기능 영향도 확인
- [ ] 인증/인가 동작 확인
- [ ] 데이터베이스 마이그레이션 확인

#### ✅ 문서 업데이트
- [ ] API 문서 업데이트
- [ ] README.md 업데이트
- [ ] 개발 가이드 업데이트
- [ ] 변경사항 CHANGELOG 작성

### 3. 충돌 해결 가이드

#### 모델 충돌 시
```python
# 충돌 예방: 마이그레이션 파일명에 타임스탬프 사용
# YYYY_MM_DD_HHMMSS_description.py

# 충돌 해결: 모델 변경사항 조율
# 1. 팀원과 스키마 변경 협의
# 2. 기존 데이터 마이그레이션 계획 수립
# 3. 백업 후 마이그레이션 실행
```

#### 라우터 충돌 시
```python
# 중복 엔드포인트 방지
# prefix 사용으로 네임스페이스 분리

# ❌ 잘못된 예시
@router.get("/list")  # 중복 가능성

# ✅ 올바른 예시  
@router.get("/tasks/")  # 명확한 리소스 구분
```

---

## 📚 API 문서화

### 1. FastAPI 자동 문서화 활용

```python
# 상세한 API 문서화 예시
@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="태스크 생성",
    description="새로운 태스크를 생성합니다.",
    responses={
        201: {"description": "태스크 생성 성공"},
        400: {"description": "잘못된 요청 데이터"},
        401: {"description": "인증 필요"},
        404: {"description": "프로젝트를 찾을 수 없음"}
    }
)
def create_task(
    task_data: TaskCreate = Body(..., example={
        "title": "새로운 태스크",
        "description": "태스크 상세 설명",
        "project_id": 1,
        "due_date": "2024-12-31T23:59:59"
    }),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token)
):
    """
    새로운 태스크를 생성합니다.
    
    - **title**: 태스크 제목 (필수)
    - **description**: 태스크 설명 (선택)
    - **project_id**: 소속 프로젝트 ID (필수)
    - **due_date**: 마감일 (선택)
    """
    pass
```

### 2. 스키마 문서화

```python
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="태스크 제목")
    description: Optional[str] = Field(None, max_length=1000, description="태스크 설명")
    project_id: int = Field(..., gt=0, description="프로젝트 ID")
    due_date: Optional[datetime] = Field(None, description="마감일")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "API 문서 작성",
                "description": "FastAPI 자동 문서화 설정",
                "project_id": 1,
                "due_date": "2024-12-31T23:59:59"
            }
        }
```

---

## 🧪 테스트 가이드

### 1. 단위 테스트

```python
# tests/test_auth.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_register_user():
    """회원가입 테스트"""
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "password123!",
        "password_confirm": "password123!",
        "name": "테스트유저"
    })
    assert response.status_code == 201
    assert response.json()["message"] == "회원가입 성공"

def test_login_user():
    """로그인 테스트"""
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123!"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### 2. 통합 테스트

```python
# tests/test_integration.py
def test_full_workflow():
    """전체 워크플로우 테스트"""
    # 1. 회원가입
    register_response = client.post("/api/v1/auth/register", json=user_data)
    
    # 2. 로그인
    login_response = client.post("/api/v1/auth/login", json=login_data)
    token = login_response.json()["access_token"]
    
    # 3. 워크스페이스 생성
    headers = {"Authorization": f"Bearer {token}"}
    workspace_response = client.post("/api/v1/workspaces/", 
                                   json=workspace_data, headers=headers)
    
    # 4. 프로젝트 생성
    project_response = client.post("/api/v1/projects/", 
                                 json=project_data, headers=headers)
    
    assert workspace_response.status_code == 201
    assert project_response.status_code == 201
```

---

## 🗄️ 데이터베이스 관리

### 1. 마이그레이션 가이드

```python
# 새로운 컬럼 추가 시
# 1. 모델 수정
class User(Base):
    # 기존 필드들...
    profile_image = Column(String, nullable=True)  # 새 필드 추가

# 2. 마이그레이션 스크립트 생성
# migrations/add_profile_image_to_user.py
def upgrade():
    """Add profile_image column to users table"""
    op.add_column('users', sa.Column('profile_image', sa.String(), nullable=True))

def downgrade():
    """Remove profile_image column from users table"""
    op.drop_column('users', 'profile_image')
```

### 2. 데이터베이스 시딩

```python
# scripts/seed_data.py
def create_test_data():
    """개발용 테스트 데이터 생성"""
    db = SessionLocal()
    
    # 테스트 사용자 생성
    test_user = User(
        email="admin@example.com",
        password=bcrypt.hashpw("admin123!".encode(), bcrypt.gensalt()).decode(),
        name="관리자",
        provider="local"
    )
    db.add(test_user)
    db.commit()
```

---

## 🔒 보안 가이드

### 1. 인증/인가 체크리스트

- [ ] JWT 토큰 만료 시간 적절히 설정
- [ ] Refresh Token 로테이션 구현
- [ ] 비밀번호 복잡도 검증
- [ ] SQL Injection 방지 (ORM 사용)
- [ ] CORS 설정 (운영환경에서 제한)

### 2. 민감 정보 처리

```python
# ❌ 잘못된 예시
SECRET_KEY = "my_secret_key"  # 하드코딩 금지

# ✅ 올바른 예시
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback_for_dev_only")

# 로깅 시 민감 정보 제외
@router.post("/login")
def login(request: LoginRequest):
    logger.info(f"Login attempt for email: {request.email}")
    # password는 로깅하지 않음
```

---

## 🚀 배포 가이드

### 1. 환경별 설정

```python
# config/settings.py
class Settings:
    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.debug = self.environment == "development"
        self.cors_origins = self._get_cors_origins()
    
    def _get_cors_origins(self):
        if self.environment == "production":
            return ["https://yourdomain.com"]
        else:
            return ["*"]  # 개발환경만
```

### 2. Docker 배포

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=software_engineering
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
```

---

## 🔧 트러블슈팅

### 1. 자주 발생하는 문제들

#### CORS 오류
```python
# 해결: main.py에서 CORS 설정 확인
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 프론트엔드 주소 확인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### JWT 토큰 오류
```python
# 해결: 토큰 만료 시간 및 시크릿 키 확인
# backend/utils/jwt_utils.py에서 설정 확인
```

#### 데이터베이스 연결 오류
```python
# 해결: 데이터베이스 URL 및 연결 상태 확인
from backend.database.base import check_db_connection
check_db_connection()  # main.py에서 호출
```

### 2. 디버깅 도구

```python
# 로깅 설정
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 사용 예시
@router.post("/debug-endpoint")
def debug_endpoint():
    logger.info("Debug endpoint called")
    logger.error("Error occurred", exc_info=True)
```

---

## 📞 팀 협업 규칙

### 1. 코드 리뷰 가이드라인

- **모든 PR은 최소 1명의 리뷰 필요**
- **리뷰 시 확인사항**:
  - [ ] 코드 스타일 일관성
  - [ ] 보안 취약점 확인
  - [ ] 성능 영향도 검토
  - [ ] 테스트 커버리지 확인

### 2. 커밋 메시지 규칙

```bash
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 수정
style: 코드 스타일 변경
refactor: 리팩토링
test: 테스트 추가/수정
chore: 빌드 설정 등 기타 변경

# 예시
feat: 태스크 관리 API 추가
fix: JWT 토큰 만료 처리 오류 수정
docs: API 문서 업데이트
```

### 3. 이슈 관리

```markdown
## 버그 리포트 템플릿
### 현상
- 무엇이 잘못되었나요?

### 재현 방법
1. 단계별 재현 과정

### 예상 결과
- 어떻게 동작해야 하나요?

### 환경
- OS: 
- Python 버전:
- 브라우저:
```

---

## 📝 참고 자료

### 1. 공식 문서
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [SQLAlchemy 문서](https://docs.sqlalchemy.org/)
- [Pydantic 문서](https://docs.pydantic.dev/)

### 2. 내부 문서
- [API 엔드포인트 변경사항](./README.md#api-엔드포인트-변경사항)
- [현재 프로젝트 구조](./README.md#프로젝트-구조)

### 3. 유용한 도구
- **API 테스트**: Postman, Insomnia
- **데이터베이스 관리**: DBeaver, pgAdmin
- **코드 품질**: pylint, black, mypy

---

## 🎯 마무리

이 가이드를 통해 팀원들이 일관된 방식으로 개발하고, 효율적으로 협업할 수 있기를 바랍니다.

**궁금한 사항이나 개선 제안이 있다면 언제든 이슈를 생성해주세요!**

---

📝 **마지막 업데이트**: 2024년 12월  
🔄 **버전**: v2.0  
👥 **관리자**: Backend Development Team 