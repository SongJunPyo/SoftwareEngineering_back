# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 개발 명령어

### 서버 실행
```bash
# 개발 서버 시작
python main.py

# 또는 uvicorn으로 직접 실행
uvicorn main:app --host 0.0.0.0 --port 8005 --reload
```

### 데이터베이스 관리
```bash
# 데이터베이스 연결 확인
python -c "from backend.database.base import check_db_connection; check_db_connection()"

# 모든 테이블 생성 (main.py에서 자동 처리됨)
python -c "from backend.database.base import engine; from backend.models import user, workspace, project; user.Base.metadata.create_all(bind=engine)"
```

### API 문서 접근
- Swagger UI: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc
- 헬스 체크: http://localhost:8005/health

## 아키텍처 개요

### 애플리케이션 구조
FastAPI 기반의 계층화된 백엔드 아키텍처:
- **Routers**: HTTP 엔드포인트와 요청/응답 로직 처리
- **Models**: SQLAlchemy ORM 모델로 데이터베이스 스키마 정의
- **Middleware**: 인증 및 인가 미들웨어
- **Utils**: JWT 토큰 관리 및 공통 유틸리티
- **Config**: 환경 변수 및 애플리케이션 설정

### 핵심 아키텍처 패턴
1. **JWT 기반 인증**: Access Token (60분) + Refresh Token (7일)
2. **OAuth 통합**: 카카오, 네이버, 구글 로그인 지원
3. **데이터베이스 세션 관리**: `get_db()` 의존성 주입을 통한 SQLAlchemy 세션
4. **구조화된 라우팅**: `/api/v1/` 하위의 기능별 라우터 조직화

### 핵심 모델 관계
- **User**: 워크스페이스와 프로젝트와의 관계를 가진 중심 엔티티
- **Workspace**: 프로젝트 조직화를 위한 컨테이너
- **Project**: 워크스페이스와 사용자에 속하며, 순서 관리 기능 포함
- **추가 모델들**: task.py, tag.py, comment_file.py, logs_notification.py (확장 기능)

### 인증 플로우
1. 사용자가 `/api/v1/auth/` 엔드포인트를 통해 회원가입/로그인
2. 사용자 정보(user_id, email)가 포함된 JWT 토큰 발급
3. 보호된 엔드포인트는 `Authorization: Bearer <token>` 헤더 필요
4. `verify_token` 의존성이 토큰 검증 및 현재 사용자 추출
5. OAuth 플로우는 `/api/v1/oauth/`에서 제공업체별 엔드포인트로 처리

### 데이터베이스 설정
- 프로덕션에서 PostgreSQL 사용 (.env의 DATABASE_URL)
- 개발환경에서 SQLite 폴백
- SQLAlchemy를 통한 연결 풀링 및 세션 관리
- 시작 시 테이블 자동 생성

### 필수 환경 변수
```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
JWT_SECRET_KEY=your_super_secret_jwt_key_change_in_production
KAKAO_CLIENT_ID=your_kakao_client_id
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
```

### API 엔드포인트 구조
- `/api/v1/auth/` - 회원가입, 로그인, 토큰 갱신, 이메일 검증
- `/api/v1/oauth/` - 카카오, 네이버, 구글 OAuth 로그인/회원가입
- `/api/v1/workspaces/` - 워크스페이스 관리 CRUD 작업
- `/api/v1/projects/` - 프로젝트 관리 CRUD 작업
- `/api/v1/projects/order` - 프로젝트 순서 및 워크스페이스 이동

### CORS 설정
현재 개발용으로 모든 오리진(`*`) 허용. 프로덕션에서는 ALLOWED_ORIGINS 환경 변수를 통해 특정 프론트엔드 도메인으로 제한해야 함.

### 코드 관례
- 모든 모델은 `Base` (SQLAlchemy declarative base)를 상속
- 라우터 모듈은 적절한 prefix와 tags를 가진 FastAPI의 `APIRouter` 사용
- 인증이 필요한 엔드포인트는 `Depends(verify_token)` 의존성 사용
- 데이터베이스 세션은 `Depends(get_db)`를 통해 주입
- 모든 datetime 필드에 UTC 타임존 사용
- 요청/응답 검증을 위한 Pydantic 스키마는 `schemas/` 디렉토리에 위치

### 개발 시 주의사항
- 레거시 라우터 `register.py`와 `login.py`는 사용 중단, `auth.py` 사용
- 모든 테이블 생성은 시작 시 자동 처리
- 애플리케이션 시작 시 데이터베이스 연결 검증
- 적절한 HTTP 상태 코드와 함께 FastAPI 관례를 따르는 오류 처리