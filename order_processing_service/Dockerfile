
# Python 3.9을 기반 이미지로 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 및 설치
COPY requirements.txt requirements.txt
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# 네트워크 디버깅 도구 설치
RUN apt-get update && apt-get install -y iputils-ping netcat-traditional && rm -rf /var/lib/apt/lists/*

# 소스 코드 복사
COPY . .

# 8002 포트로 서비스 노출
EXPOSE 8002

# Uvicorn을 사용하여 애플리케이션 실행 (임시로 네트워크 테스트 스크립트로 변경)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--log-level", "debug"]
