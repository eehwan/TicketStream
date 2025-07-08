
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
import json

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

producer: KafkaProducer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global producer
    logger.info("Attempting to connect to Kafka producer...")
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=['kafka:9092'], # Docker Compose 내부에서 접근할 주소
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            logger.info("Kafka Producer connected successfully!")
            break
        except NoBrokersAvailable as e:
            logger.error(f"Kafka broker not available for producer: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred during Kafka producer initialization: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
    yield
    # 애플리케이션 종료 시 프로듀서 닫기 (선택 사항)
    if producer:
        producer.close()

app = FastAPI(lifespan=lifespan)

@app.post("/api/reservations/")
def create_reservation(reservation: dict):
    """
    예매 요청을 받아 Kafka 토픽으로 전송합니다.
    MVP 버전에서는 간단한 dict 형태로 데이터를 받습니다.
    예: {"event_id": 1, "user_id": 123, "seat_id": "A1"}
    """
    if producer is None:
        return {"status": "error", "message": "Kafka producer is not initialized."}
    try:
        # 'reservation-topic'으로 메시지 전송
        producer.send('reservation-topic', value=reservation)
        producer.flush() # 메시지가 완전히 전송되도록 보장
        return {"status": "success", "message": "Reservation request received and is being processed."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def health_check():
    return {"status": "ok"}

