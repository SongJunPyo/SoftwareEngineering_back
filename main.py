from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import auth, oauth, workspace, project, project_order, notifications, project_members, workspace_project_order, user_setting, task, task_project_member, comment, user_delete, user_password, dashboard
from backend.routers import tag as tag_router
from backend.routers import user_profile
from backend.websocket import websocket_router
from backend.database.base import engine, check_db_connection
from backend.models import user, workspace as workspace_model, project as project_model, project_invitation, logs_notification, workspace_project_order as wpo_model, user_setting as user_setting_model, tag, task as task_model
from backend.routers import deadline_notification
from backend.routers import logs

# 데이터베이스 연결 확인
check_db_connection()

# 데이터베이스 테이블 생성
user.Base.metadata.create_all(bind=engine)
workspace_model.Base.metadata.create_all(bind=engine)
project_model.Base.metadata.create_all(bind=engine)
project_invitation.Base.metadata.create_all(bind=engine)
logs_notification.Base.metadata.create_all(bind=engine)
wpo_model.Base.metadata.create_all(bind=engine)
user_setting_model.Base.metadata.create_all(bind=engine)
tag.Base.metadata.create_all(bind=engine)
task_model.Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Software Engineering Backend API",
    description="소프트웨어 공학 백엔드 API - 정리된 구조",
    version="2.0.0"
)


# CORS 설정 (개발 환경용 - 모든 Origin 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 Origin 허용 (개발 환경용)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# 라우터 등록 (새로운 구조)
app.include_router(auth.router)          # 인증 관련 (회원가입, 로그인, 토큰 갱신)
app.include_router(oauth.router)         # OAuth 로그인 (카카오, 네이버, 구글)
app.include_router(workspace.router)     # 워크스페이스 CRUD
app.include_router(project.router)       # 프로젝트 CRUD
app.include_router(project_order.router) # 프로젝트 순서 관리
app.include_router(workspace_project_order.router) # 워크스페이스-프로젝트 관계 관리
app.include_router(user_setting.router)  # 사용자 설정 관리
app.include_router(notifications.router) # 알림 관리
app.include_router(project_members.router) # 프로젝트 멤버 초대 및 관리
app.include_router(task.router)          # 업무(Task) CRUD
app.include_router(task_project_member.router) # 프로젝트 멤버 관리
app.include_router(comment.router)        # 댓글 관리
app.include_router(tag_router.router)     # 태그 관리
app.include_router(logs.router)
app.include_router(user_delete.router)
app.include_router(user_password.router)
app.include_router(user_profile.router)
app.include_router(dashboard.router)     # 대시보드 데이터
app.include_router(websocket_router.router)  # WebSocket 실시간 통신

@app.get("/")
def read_root():
    return {
        "message": "Software Engineering Backend API v2.0",
        "status": "구조화 완료",
        "features": [
            "JWT 기반 인증/인가",
            "기능별 분리된 라우터",
            "OAuth 로그인 지원",
            "워크스페이스 및 프로젝트 관리",
            "프로젝트 멤버 초대 시스템",
            "알림 관리 시스템"
        ],
        "deprecated_files": [
            "backend/routers/register.py - 사용 중단",
            "backend/routers/login.py - 사용 중단"
        ],
        "cors_status": "모든 Origin 허용 (개발 환경)"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "cors": "permissive"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,  # 원래 FastAPI 앱 실행
        host="0.0.0.0", 
        port=8005,
        log_level="debug"
    ) 