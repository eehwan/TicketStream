
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY requirements.txt requirements.txt
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/order_service

EXPOSE 8002

CMD ["uvicorn", "order_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
