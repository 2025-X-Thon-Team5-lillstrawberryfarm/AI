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

# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 1) 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) 소스 전체 복사
COPY . .

# Cloud Run이 기본으로 PORT 환경 변수 설정해줌 (기본 8080)
ENV PORT=8080

# 3) Gunicorn + UvicornWorker 로 FastAPI 실행
#   main.py 안의 app 인스턴스를 사용 -> main:app
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "0", "--bind", "0.0.0.0:8080", "-k", "uvicorn.workers.UvicornWorker", "main:app"]