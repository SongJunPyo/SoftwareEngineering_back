from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import auth, oauth, workspace, project, project_order
from backend.database.base import engine, check_db_connection
from backend.models import user, workspace as workspace_model, project as project_model
from backend.config.settings import ALLOWED_ORIGINS

# 데이터베이스 연결 확인
check_db_connection()

# 데이터베이스 테이블 생성
user.Base.metadata.create_all(bind=engine)
workspace_model.Base.metadata.create_all(bind=engine)
project_model.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Software Engineering Backend API",
    description="소프트웨어 공학 백엔드 API - 정리된 구조",
    version="2.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(workspace.router)
app.include_router(project.router)
app.include_router(project_order.router)

@app.get("/")
def read_root():
    return {
        "message": "Software Engineering Backend API v2.0",
        "status": "구조화 완료",
        "features": [
            "JWT 기반 인증/인가",
            "기능별 분리된 라우터",
            "OAuth 로그인 지원",
            "워크스페이스 및 프로젝트 관리"
        ],
        "cors_status": f"허용된 Origin: {ALLOWED_ORIGINS}"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "cors": "configured"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    ) 