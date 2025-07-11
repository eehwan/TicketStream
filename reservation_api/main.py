import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from sqlalchemy.orm import Session

import json
import os

from reservation_api.database import Base, engine, get_db
from reservation_api.models import ReservationAttempt
from reservation_api import crud, schemas
from common.tracing import setup_telemetry # common 모듈 임포트

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

producer: AIOKafkaProducer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Setting up OpenTelemetry...")
    setup_telemetry(app) # 공통 함수 호출
    logger.info("OpenTelemetry setup complete.")

    global producer
    logger.info("Attempting to connect to Kafka producer...")
    loop = asyncio.get_event_loop()
    while True:
        try:
            producer = AIOKafkaProducer(
                loop=loop,
                bootstrap_servers='kafka:9092', # Docker Compose 내부에서 접근할 주소
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await producer.start()
            logger.info("Kafka Producer connected successfully!")
            break
        except KafkaConnectionError as e:
            logger.error(f"Kafka broker not available for producer: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred during Kafka producer initialization: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

    logger.info("Creating database tables for Reservation API...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Reservation API database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating Reservation API database tables: {e}")
    yield
    # 애플리케이션 종료 시 프로듀서 닫기
    if producer:
        await producer.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/api/reservations/", response_model=schemas.ReservationAttempt)
async def create_reservation(
    reservation_request: schemas.ReservationAttemptCreate,
    db: Session = Depends(get_db)
):
    """
    예매 요청을 받아 Kafka 토픽으로 전송합니다.
    예: {"event_id": 1, "user_id": 123, "seat_id": "A1"}
    """
    if producer is None:
        raise HTTPException(status_code=503, detail="Kafka producer is not initialized.")
    try:
        reservation_attempt_id = str(uuid4())
        
        # Save reservation attempt to database using CRUD function
        new_attempt = crud.create_reservation_attempt(db, reservation_request, reservation_attempt_id)
        logger.info(f"Reservation attempt {reservation_attempt_id} saved to DB.")

        # Prepare the event data
        event_data = {
            "reservation_attempt_id": new_attempt.reservation_attempt_id,
            "user_id": new_attempt.user_id,
            "event_id": new_attempt.event_id,
            "seat_id": new_attempt.seat_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        # 'reservation_attempts' 토픽으로 메시지 전송
        await producer.send_and_wait('reservation_attempts', value=event_data)
        logger.info(f"Reservation attempt {reservation_attempt_id} sent to Kafka.")

        return new_attempt # Return the created reservation attempt object
    except Exception as e:
        db.rollback() # Rollback in case of error
        logger.error(f"Failed to process reservation request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process reservation request: {e}")

@app.get("/")
def health_check():
    return {"status": "ok"}