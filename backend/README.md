# Software Engineering Backend API v2.0

## 📁 프로젝트 구조

```
backend/
├── config/
│   ├── __init__.py
│   └── settings.py          # 환경 설정 (JWT, OAuth)
├── database/
│   └── base.py              # 데이터베이스 연결
├── middleware/
│   ├── __init__.py
│   └── auth.py              # JWT 인증/인가 미들웨어
├── models/
│   ├── user.py              # 사용자 모델
│   ├── workspace.py         # 워크스페이스 모델
│   └── project.py           # 프로젝트 모델
├── routers/
│   ├── auth.py              # 일반 회원가입/로그인
│   ├── oauth.py             # OAuth 로그인 (카카오, 네이버, 구글)
│   ├── workspace.py         # 워크스페이스 CRUD
│   ├── project.py           # 프로젝트 CRUD
│   └── project_order.py     # 프로젝트 순서 관리
├── schemas/
│   └── LojginSignUP.py      # Pydantic 스키마
├── utils/
│   ├── __init__.py
│   └── jwt_utils.py         # JWT 토큰 유틸리티
└── main.py                  # FastAPI 앱 설정
```

## 🚀 주요 기능

### 1. 인증/인가 시스템
- **JWT 기반 인증**: Access Token + Refresh Token
- **OAuth 로그인**: 카카오, 네이버, 구글 지원
- **토큰 자동 갱신**: Refresh Token을 통한 Access Token 갱신

### 2. API 엔드포인트

#### 인증 관련 (`/api/v1/auth`)
- `POST /register` - 일반 회원가입
- `POST /login` - 로그인
- `POST /refresh` - 토큰 갱신
- `POST /check-email` - 이메일 중복 확인

#### OAuth 로그인 (`/api/v1/oauth`)
- `POST /kakao` - 카카오 로그인
- `POST /kakao/register` - 카카오 회원가입
- `POST /naver` - 네이버 로그인
- `POST /google` - 구글 로그인
- `POST /google/register` - 구글 회원가입

#### 워크스페이스 관리 (`/api/v1/workspaces`)
- `POST /` - 워크스페이스 생성
- `GET /` - 워크스페이스 목록 조회
- `GET /{workspace_id}` - 워크스페이스 상세 조회
- `PUT /{workspace_id}` - 워크스페이스 수정
- `DELETE /{workspace_id}` - 워크스페이스 삭제

#### 프로젝트 관리 (`/api/v1/projects`)
- `POST /` - 프로젝트 생성
- `GET /` - 프로젝트 목록 조회 (워크스페이스 필터링 가능)
- `GET /{project_id}` - 프로젝트 상세 조회
- `PUT /{project_id}` - 프로젝트 수정
- `DELETE /{project_id}` - 프로젝트 삭제
- `PUT /order` - 프로젝트 순서 변경
- `PUT /{project_id}/move` - 프로젝트 워크스페이스 이동

## 🔧 설정

### 환경 변수
```bash
JWT_SECRET_KEY=your_super_secret_jwt_key_change_in_production
```

### OAuth 설정
- **카카오**: `KAKAO_CLIENT_ID`, `KAKAO_REDIRECT_URI`
- **네이버**: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
- **구글**: 프론트엔드에서 처리

## 🛡️ 보안

### JWT 토큰 구조
```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "exp": 1234567890,
  "type": "access" // 또는 "refresh"
}
```

### 인증 헤더
```
Authorization: Bearer <access_token>
```

## 📝 사용 예시

### 1. 회원가입
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123!",
    "password_confirm": "password123!",
    "name": "홍길동"
  }'
```

### 2. 로그인
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123!"
  }'
```

### 3. 워크스페이스 생성 (인증 필요)
```bash
curl -X POST "http://localhost:8000/api/v1/workspaces/" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "내 워크스페이스",
    "description": "프로젝트 관리용 워크스페이스"
  }'
```

## 🔄 마이그레이션 가이드

### 기존 코드에서 새 구조로 변경

#### Before (기존)
```python
from backend.routers.register import router as register_router
from backend.routers.login import router as login_router
```

#### After (새 구조)
```python
from backend.routers.auth import router as auth_router
from backend.routers.oauth import router as oauth_router
from backend.routers.workspace import router as workspace_router
from backend.routers.project import router as project_router
```

## 🚨 주의사항

1. **기존 파일들**: `register.py`, `login.py`는 더 이상 사용되지 않습니다.
2. **JWT 설정**: 운영 환경에서는 반드시 강력한 JWT_SECRET_KEY를 설정하세요.
3. **CORS 설정**: 프론트엔드 도메인에 맞게 CORS 설정을 조정하세요.
4. **데이터베이스**: 모델 변경 시 마이그레이션을 수행하세요.

## 🔍 API 문서

서버 실행 후 다음 URL에서 자동 생성된 API 문서를 확인할 수 있습니다:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc` 