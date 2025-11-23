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

# --- SQL Helpers (기존과 동일) ---
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

# --- AI Function (조건부 로직 적용) ---
def generate_ai_response(user_msg, curr_data, prev_data, target_budget, history):
    # 1. 목표 금액이 설정되지 않은 경우 (0원 혹은 None)
    if not target_budget or int(target_budget) == 0:
        system_prompt = """
        당신은 사용자의 자산 관리를 돕기 위해 초기 설정을 진행하는 AI 비서입니다.
        현재 사용자는 '목표 소비 금액'을 설정하지 않은 상태입니다.
        
        [행동 지침]:
        1. 사용자의 메시지가 "시작", "안녕", "하이" 등 단순한 입장 신호이거나 대화의 시작이라면:
           - 반드시 다음 문장으로 답변을 시작하세요: "당신의 목표 소비 금액은 얼마인가요?"
           
        2. 사용자가 목표 금액을 말하지 않고 다른 질문을 하거나 답변을 회피한다면:
           - 자산 관리를 위해서는 목표 설정이 필수적임을 알리고, 반드시 다음 문장 형식을 사용하여 답변하세요:
             "당신의 소비 습관 증진을 위해 조언해줄 수 있도록 목표 소비 금액을 제시해주면 감사하겠습니다."
             
        3. 사용자가 숫자로 금액을 이야기한다면(예: "50만원", "300000"):
           - "목표 금액이 설정되었습니다. 이제 소비 내역을 분석해드릴까요?"라고 답변하고 대화를 이어가세요.
        """
        
    # 2. 목표 금액이 설정된 경우 (기존 로직 수행)
    else:
        system_prompt = f"""
        당신은 사용자가 설정한 '목표 소비 금액({target_budget}원)' 달성을 돕는 'AI 자산 관리 비서'입니다.
        현재 소비 내역과 지난달 내역을 비교하여 현실적인 조언을 제공하세요.
        
        [데이터 1: 이번 달 현황]: {json.dumps(curr_data, ensure_ascii=False)}
        [데이터 2: 지난 달 내역]: {json.dumps(prev_data, ensure_ascii=False)}
        
        [조언 생성 원칙 (엄격 준수)]:
        1. **절약 1순위 그룹 집중 공략**: [유흥/술, 택시/배달, 쇼핑] 중 증가/비중 큰 항목 우선 지적.
        2. **고정비 건드리기 금지**: 월세, 공과금, 보험료 등은 제외.
        3. **비교 분석 활용**: 구체적 수치("지난달보다 10만원 증가") 언급.
        4. **단계적 제안**: "하지 마세요" 대신 "줄여볼까요?" 또는 대체재 제안.
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
        # 참고: 프론트엔드에서 '입장 신호(예: init_signal)'를 보낼 경우, DB에 저장하지 않도록 처리할 수도 있습니다.
        # 여기서는 모든 메시지를 저장한다고 가정합니다.
        save_chat_message(cursor, user_id, 'USER', req.message)
        db.commit()

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
