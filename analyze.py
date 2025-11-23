import os
import json
import datetime
from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI
from database import get_db
from schemas import UserRequest
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])

ANALYZE_API_KEY = os.getenv("ANALYZE_API_KEY")
client = OpenAI(api_key=ANALYZE_API_KEY)
MODEL_NAME = "gpt-4o"

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

def get_group_averages(cursor, user_id, year, month):
    # 1. 내 cluster_id 찾기
    cursor.execute("SELECT cluster_id FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user or not user['cluster_id']: return {"summary": {}, "total": 0}
    
    # 2. 그룹 평균 계산
    sql = """
        SELECT t.category, AVG(t.amount) as avg_amount
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        WHERE u.cluster_id = %s AND t.transacted_at LIKE %s AND t.type = 'WITHDRAW'
        GROUP BY t.category
    """
    month_str = f"{year}-{month:02d}%"
    cursor.execute(sql, (user['cluster_id'], month_str))
    result = cursor.fetchall()
    summary = {row['category']: int(row['avg_amount']) for row in result}
    return {"summary": summary, "total": sum(summary.values())}

def get_user_cluster_info(cursor, user_id):
    sql = """
        SELECT c.min_amount, c.max_amount
        FROM users u JOIN clusters c ON u.cluster_id = c.id
        WHERE u.id = %s
    """
    cursor.execute(sql, (user_id,))
    return cursor.fetchone()

# =========================================================
#  [AI] 분석 로직
# =========================================================

def generate_ai_report(m2_data, m1_data, group_data, cluster_info, range_text):
    prompt = f"""
    당신은 '금융 데이터 분석가'입니다. 조언은 하지 말고, 주어진 데이터를 분석하여 팩트만 서술하세요.
    
    [데이터 셋]
    1. 저저번 달 내 소비: {json.dumps(m2_data, ensure_ascii=False)}
    2. 저번 달 내 소비: {json.dumps(m1_data, ensure_ascii=False)}
    3. 저번 달 그룹 평균: {json.dumps(group_data, ensure_ascii=False)}
    4. 내 소비구간: {range_text}

    [작성 요구사항 (순서대로 작성하세요)]
    1. 'section_past_comparison': 
       - 저저번 달 대비 저번 달의 소비 습관 변화를 분석.
       - "전체 소비는 X원(Y%) 증가/감소했습니다." 포함.
       - 카테고리별 변화 팩트 위주 서술.

    2. 'section_cluster_info': 
       - 정확히 "당신은 소비구간 {range_text} 구간에 속해 있습니다." 라고만 작성.

    3. 'section_group_comparison': 
       - 저번 달 내 소비와 그룹 평균을 비교.
       - 어떤 부분(카테고리)에 소비를 더 많이 했거나 덜 했는지 명시적으로 서술.

    [출력 형식 (JSON Only)]:
    {{
        "section_past_comparison": "...",
        "section_cluster_info": "...",
        "section_group_comparison": "..."
    }}
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {}

# =========================================================
#  [API] 엔드포인트
# =========================================================

@router.post("/report")
def get_monthly_report(req: UserRequest, db=Depends(get_db)):
    user_id = req.user_id
    
    # 1. 날짜 계산 (오늘 기준 지난달 리포트)
    today = datetime.date.today()
    first_day_curr = today.replace(day=1)
    last_month_date = first_day_curr - datetime.timedelta(days=1)
    report_month_key = last_month_date.strftime("%Y-%m")
    
    m1_year, m1_month = last_month_date.year, last_month_date.month
    two_months_ago = last_month_date.replace(day=1) - datetime.timedelta(days=1)
    m2_year, m2_month = two_months_ago.year, two_months_ago.month

    with db.cursor() as cursor:
        # -------------------------------------------------------
        # STEP 1: 캐시 확인 (DB에 이미 있는지?)
        # -------------------------------------------------------
        sql_check = """
            SELECT formatted_text FROM analysis_reports 
            WHERE user_id = %s AND report_month = %s 
            LIMIT 1
        """
        cursor.execute(sql_check, (user_id, report_month_key))
        existing_report = cursor.fetchone()

        if existing_report:
            return {
                "status": "cached",
                "report_text": existing_report['formatted_text']
            }

        # -------------------------------------------------------
        # STEP 2: 없으면 데이터 수집
        # -------------------------------------------------------
        data_m2 = get_monthly_summary(cursor, user_id, m2_year, m2_month)
        data_m1 = get_monthly_summary(cursor, user_id, m1_year, m1_month)
        group_m1 = get_group_averages(cursor, user_id, m1_year, m1_month)
        cluster_info = get_user_cluster_info(cursor, user_id)

        range_text = "정보 없음"
        if cluster_info:
            min_v = int(cluster_info['min_amount']) // 10000
            max_v = int(cluster_info['max_amount']) // 10000
            range_text = f"{min_v}만원~{max_v}만원"

        # -------------------------------------------------------
        # STEP 3: AI 분석 실행
        # -------------------------------------------------------
        ai_json = generate_ai_report(data_m2, data_m1, group_m1, cluster_info, range_text)

        # 화면 출력용 텍스트 조립
        final_text = f"""[{m2_month}월 소비 vs {m1_month}월 소비]
{ai_json.get('section_past_comparison', '데이터 부족')}

----------------------------------------
[속한 그룹과의 비교]
{ai_json.get('section_cluster_info', '데이터 부족')}
{ai_json.get('section_group_comparison', '데이터 부족')}"""

        # -------------------------------------------------------
        # STEP 4: DB 저장 (INSERT)
        # -------------------------------------------------------
        sql_save = """
            INSERT INTO analysis_reports 
            (user_id, report_month, raw_json, formatted_text, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """
        cursor.execute(sql_save, (user_id, report_month_key, json.dumps(ai_json, ensure_ascii=False), final_text))
        db.commit()

        return {
            "status": "created",
            "report_text": final_text
        }
