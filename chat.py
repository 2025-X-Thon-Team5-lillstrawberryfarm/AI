import json
import datetime
from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI
from database import get_db 
from schemas import ChatRequest
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/chat", tags=["Chatbot"])

CHATBOT_API_KEY = os.getenv("CHATBOT_API_KEY")

client = OpenAI(api_key=CHATBOT_API_KEY)

MODEL_NAME = "gpt-4o"

# --- SQL Helpers ---
def get_monthly_summary(cursor, user_id, year, month):
    sql = """
        SELECT category, SUM(amount) as total_amount
        FROM transactions
        WHERE user_id = %s AND transacted_at LIKE %s AND type = 'WITHDRAW'
        GROUP BY category
    """
    month_str = f"{year}-{month:02d}%"
    cursor.execute(sql, (user_id, month_str))
    result = cursor.fetchall()
    summary = {row['category']: int(row['total_amount']) for row in result}
    return {"summary": summary, "total": sum(summary.values())}

def get_chat_history(cursor, user_id, limit=6):
    sql = "SELECT sender, content FROM chat_messages WHERE user_id = %s ORDER BY created_at DESC LIMIT %s"
    cursor.execute(sql, (user_id, limit))
    rows = cursor.fetchall()
    history = []
    for row in rows:
        role = "user" if row['sender'] == "USER" else "assistant"
        history.append({"role": role, "content": row['content']})
    return history[::-1]

def save_chat_message(cursor, user_id, sender, content):
    sql = "INSERT INTO chat_messages (user_id, sender, content, created_at) VALUES (%s, %s, %s, NOW())"
    cursor.execute(sql, (user_id, sender, content))

# --- AI Function (상세 프롬프트 적용) ---
def generate_ai_response(user_msg, curr_data, prev_data, target_budget, history):
    system_prompt = f"""
    당신은 사용자가 설정한 '목표 소비 금액({target_budget}원)' 달성을 돕는 'AI 자산 관리 비서'입니다.
    현재 소비 내역과 지난달 내역을 비교하여 현실적인 조언을 제공하세요.
    
    [데이터 1: 이번 달 현황]: {json.dumps(curr_data, ensure_ascii=False)}
    [데이터 2: 지난 달 내역]: {json.dumps(prev_data, ensure_ascii=False)}
    
    [조언 생성 원칙 (엄격 준수)]:
    1. **절약 1순위 그룹 집중 공략**: 
       - [유흥/술, 택시/배달, 쇼핑] 이 세 가지 항목을 가장 먼저 확인하세요.
       - 이 중 지난달 대비 금액이 늘었거나, 지출 비중이 큰 항목을 찾아 우선적으로 줄이도록 권유하세요.
    
    2. **고정비 건드리기 금지**: 
       - 월세, 공과금, 보험료, 통신비, 저축 등은 줄이라고 하지 마세요.
    
    3. **비교 분석 활용**: 
       - "지난달보다 식비가 10만원 늘었네요" 처럼 구체적인 수치를 근거로 말하세요.
    
    4. **단계적/중립적 제안**: 
       - "아예 하지 마세요" (X) -> "횟수를 주 1회로 줄여볼까요?" (O)
       - "회사 탕비실 쓰세요" (X) -> "저가형 브랜드를 이용해보세요" (O)
       - 사용자에게 특정 직업(직장인/학생) 프레임을 씌우지 마세요.
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_msg})

    try:
        response = client.chat.completions.create(model=MODEL_NAME, messages=messages, temperature=0.7)
        return response.choices[0].message.content
    except:
        return "죄송합니다. AI 서버 연결 중 오류가 발생했습니다."

# --- Main Route ---
@router.post("")
def chat_endpoint(req: ChatRequest, db=Depends(get_db)):
    user_id = req.user_id
    
    with db.cursor() as cursor:
        # 1. 유저 질문 저장
        save_chat_message(cursor, user_id, 'USER', req.message)
        db.commit() # 즉시 저장

        # 2. 데이터 수집
        today = datetime.date.today()
        curr_data = get_monthly_summary(cursor, user_id, today.year, today.month)
        
        first = today.replace(day=1)
        last_month = first - datetime.timedelta(days=1)
        prev_data = get_monthly_summary(cursor, user_id, last_month.year, last_month.month)
        
        # 3. 히스토리 조회
        history = get_chat_history(cursor, user_id)

        # 4. 답변 생성
        bot_reply = generate_ai_response(req.message, curr_data, prev_data, req.target_budget, history)
        
        # 5. 답변 저장
        save_chat_message(cursor, user_id, 'BOT', bot_reply)
        db.commit()

    return {"reply": bot_reply}
