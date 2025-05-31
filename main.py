from fastapi import FastAPI
from backend.database.base import check_db_connection
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import register, login, project_order_router  # project_order_router 추가

check_db_connection()

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 필요에 따라 출처 제한 가능
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 라우터 등록
app.include_router(register.router)
app.include_router(login.router)
app.include_router(project_order_router)

@app.get("/")
def root():
    return {"message": "FastAPI server is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",  # 모든 IP에서 접근 허용
        port=8005,
        log_level="debug"
    )
