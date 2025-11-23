import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

# .env 파일이나 환경변수에서 가져오거나, 직접 입력하세요.
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("USER"),      # .env 파일의 변수명과 일치시켜주세요
    "password": os.getenv("PASSWORD"),
    "db": os.getenv("DB"),
    "charset": os.getenv("CHARSET"), 
    "cursorclass": pymysql.cursors.DictCursor
}

def get_db():
    """
    FastAPI 의존성 주입용 DB 세션 생성기.
    API 요청 시 연결하고, 응답 후 자동으로 연결을 닫습니다.
    """
    # 위에서 정의한 DB_CONFIG를 사용하여 연결
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()
