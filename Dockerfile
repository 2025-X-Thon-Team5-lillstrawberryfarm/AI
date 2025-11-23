# 1. 베이스 이미지 (파이썬 환경)
FROM python:3.11-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 앱 코드 전체 복사
COPY . .

# 5. 환경 변수로 포트 설정 (Cloud Run의 기본 포트 8080)
ENV PORT=8080

# 6. Uvicorn 서버 실행 명령
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
