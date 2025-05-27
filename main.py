from fastapi import FastAPI
<<<<<<< HEAD
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
# 👇 CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 프론트엔드 도메인
# 나머지 API 라우터 등 추가
@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI"}

@app.post("/api/auth/google")
def google_auth(data: dict):
    return {"message": "Google login received", "data": data}


# 라우터 등록
app.include_router(register.router)
app.include_router(login.router)

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
