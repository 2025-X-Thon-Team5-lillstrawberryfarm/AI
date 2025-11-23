import uvicorn
import pymysql
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from routers import transactions, analysis, chat, clustering
from database import DB_CONFIG 

# ---------------------------------------------------------
# ⏰ 스케줄러 설정 (매월 1일 그룹 갱신)
# ---------------------------------------------------------
def scheduled_task():
    print("⏰ [자동 실행] 월간 그룹 갱신을 시작합니다...")
    conn = pymysql.connect(**DB_CONFIG)
    try:
        clustering.logic_clustering(conn)
        print("✅ [자동 실행] 그룹 갱신 완료!")
    except Exception as e:
        print(f"❌ [자동 실행] 실패: {e}")
    finally:
        conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 켜질 때
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_task, 'cron', day='1', hour='0', minute='0')
    scheduler.start()
    print("🚀 서버 가동: 스케줄러 ON")
    
    yield # 서버 작동 중...
    
    # 서버 꺼질 때
    scheduler.shutdown()
    print("💤 서버 종료: 스케줄러 OFF")

# ---------------------------------------------------------
# 🚀 앱 초기화
# ---------------------------------------------------------
app = FastAPI(
    title="FinMate AI Server",
    description="프론트엔드 연동용 최종 API 서버",
    version="1.0.0",
    lifespan=lifespan
)

# =========================================================
# 🔓 [매우 중요] CORS 설정 (프론트엔드 접속 허용)
# =========================================================
# 이 설정이 없으면 프론트엔드(localhost:3000 등)에서 접속이 차단됩니다.
origins = [
    "http://localhost:3000", # 리액트/Next.js 기본 포트
    "http://localhost:8080", # 뷰(Vue) 기본 포트
    "http://127.0.0.1:3000",
    "*"                      
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # 허용할 사이트 목록
    allow_credentials=True,     # 쿠키/인증정보 허용 여부
    allow_methods=["*"],        # 허용할 HTTP 메서드 (GET, POST, PUT, DELETE 등 전체)
    allow_headers=["*"],        # 허용할 헤더 (전체)
)

# ---------------------------------------------------------
# 🔗 라우터 등록 (기능 연결)
# ---------------------------------------------------------
app.include_router(clustering.router)   # 관리자/그룹분석
app.include_router(chat.router)         # 챗봇
app.include_router(analysis.router)     # 리포트 분석
app.include_router(transactions.router) # 소비내역 관리


# ---------------------------------------------------------
# 👋 기본 접속 테스트
# ---------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "Hello FinMate! 프론트엔드와 연결할 준비가 되었습니다."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
