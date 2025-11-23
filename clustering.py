import uvicorn
import pymysql
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler

from routers import transactions, analysis, chat, clustering
from database import DB_CONFIG 

# ---------------------------------------------------------
# ⏰ 스케줄러가 실행할 함수 (DB 연결 수동 생성)
# ---------------------------------------------------------
def scheduled_task():
    print("⏰ [자동 실행] 월간 그룹 갱신을 시작합니다...")
    # 직접 연결을 하나 열어서 처리해야 합니다.
    conn = pymysql.connect(**DB_CONFIG)
    try:
        clustering.logic_clustering(conn) #
        print("✅ [자동 실행] 그룹 갱신 완료!")
    except Exception as e:
        print(f"❌ [자동 실행] 실패: {e}")
    finally:
        conn.close()

# ---------------------------------------------------------
# 🚀 서버 수명주기 (켜질 때 스케줄러 ON, 꺼질 때 OFF)
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 서버 시작 시
    scheduler = BackgroundScheduler()
    
    # 매월 1일 0시 0분에 실행 (timezone 설정 가능)
    scheduler.add_job(scheduled_task, 'cron', day='1', hour='0', minute='0')
    
    scheduler.start()
    print("🚀 서버 가동: 스케줄러가 시작되었습니다. (매월 1일 실행)")
    
    yield # 여기서 서버가 계속 돌아갑니다.
    
    # 2. 서버 종료 시
    scheduler.shutdown()
    print("💤 서버 종료: 스케줄러가 꺼졌습니다.")

app = FastAPI(
    title="FinMate AI Server",
    lifespan=lifespan # <--- 여기 등록 필수!
)

# 라우터 등록
app.include_router(clustering.router)
# app.include_router(transactions.router) ... 등등 기존 라우터들

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
