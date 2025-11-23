from pydantic import BaseModel
from typing import Optional, Any

# 1. 소비 내역 추가 요청
class TransactionRequest(BaseModel):
    user_id: int
    amount: float
    content: str
    date: Optional[str] = None 

# 2. 분석 요청 (월간 리포트, 분류 등)
class UserRequest(BaseModel):
    user_id: int

# 3. 챗봇 대화 요청
class ChatRequest(BaseModel):
    user_id: int
    message: str
    target_budget: int = 0
