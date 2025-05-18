from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
# 👇 CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 프론트엔드 도메인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 나머지 API 라우터 등 추가
@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI"}

@app.post("/api/auth/google")
def google_auth(data: dict):
    return {"message": "Google login received", "data": data}

