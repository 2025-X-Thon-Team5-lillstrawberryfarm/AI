import uvicorn
from fastapi import FastAPI
from routers import transactions, analysis, chat

# FastAPI 앱 초기화
app = FastAPI(
    title="FinMate AI Server",
    description="FastAPI 기반 핀테크 AI 백엔드 (트랜잭션 분류, 월간 분석, 챗봇)",
    version="1.0.0"
)

# 우리가 만든 라우터(기능) 등록
app.include_router(transactions.router) # /api/transaction
app.include_router(analysis.router)     # /api/analysis
app.include_router(chat.router)         # /api/chat

# 기본 루트 경로 (상태 확인용)
@app.get("/")
def root():
    return {"message": "🚀 FinMate AI Server is Running!"}

# 직접 실행 시 uvicorn 서버 가동
if __name__ == "__main__":
    # host="0.0.0.0"으로 설정하면 외부에서도 접속 가능
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
