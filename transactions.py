import os
import datetime
from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI
from dotenv import load_dotenv
from database import get_db
from schemas import TransactionRequest

load_dotenv()
# 라우터 설정
router = APIRouter(prefix="/api/transaction", tags=["Transactions"])

CATEGORY_API_KEY = os.getenv("CATEGORY_API_KEY")
client = OpenAI(api_key=CATEGORY_API_KEY)
MODEL_NAME = "gpt-4o"

def classify_category_ai(content):
    prompt = f"""
    소비처: "{content}"
    위 소비처를 아래 [분류 기준]에 맞춰 가장 적절한 카테고리 하나로 분류하세요.
    설명 없이 오직 카테고리 명만 단답형으로 출력하세요.

    [분류 기준]
    - 식비: 식당, 카페, 배달, 주점, 베이커리
    - 교통: 지하철, 택시, 버스, 기차, 주유소
    - 쇼핑: 의류, 쿠팡, 백화점, 잡화, 미용실
    - 의료/건강: 병원, 약국, 헬스장, 필라테스
    - 문화/여가: 영화, OTT, 게임, 여행, 숙박
    - 공과금/고정비: 월세, 관리비, 통신비, 보험료
    - 이체: 친구송금, 회비, 적금
    - 편의점/마트: 편의점, 대형마트, 슈퍼마켓
    - 기타: 위 분류에 속하지 않는 것
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20, 
            temperature=0.3 
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        return "기타"

@router.post("")
def add_transaction(req: TransactionRequest, db=Depends(get_db)):
    # 날짜 처리
    date_str = req.date if req.date else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. AI 분류
    category = classify_category_ai(req.content)

    # 2. DB 저장
    try:
        with db.cursor() as cursor:
            sql = """
                INSERT INTO transactions 
                (user_id, amount, original_content, category, transacted_at, type)
                VALUES (%s, %s, %s, %s, %s, 'WITHDRAW')
            """
            cursor.execute(sql, (req.user_id, req.amount, req.content, category, date_str))
        db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "success", 
        "category": category,
        "content": req.content
    }
