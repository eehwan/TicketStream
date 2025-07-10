
# Python 3.9을 기반 이미지로 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 및 설치
COPY requirements.txt requirements.txt
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
ENV PYTHONPATH=/app

COPY . /app/reservation_api

EXPOSE 8001

CMD ["uvicorn", "reservation_api.main:app", "--host", "0.0.0.0", "--port", "8001"]
