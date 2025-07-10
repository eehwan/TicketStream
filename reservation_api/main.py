import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

import json
import os

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터베이스 설정
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@shared_postgres_db:5432/reservation_db")
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DB 모델 정의
class ReservationAttempt(Base):
    __tablename__ = "reservation_attempts"

    id = Column(Integer, primary_key=True, index=True)
    reservation_attempt_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=False)
    event_id = Column(Integer, nullable=False)
    requested_seat_id = Column(String, nullable=False)
    status = Column(String, default="PENDING", nullable=False) # PENDING, ALLOCATED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

producer: AIOKafkaProducer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
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

@app.post("/api/reservations/")
async def create_reservation(
    reservation_request: dict, # Renamed for clarity
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
        
        # Save reservation attempt to database
        new_attempt = ReservationAttempt(
            reservation_attempt_id=reservation_attempt_id,
            user_id=reservation_request.get("user_id"),
            event_id=reservation_request.get("event_id"),
            requested_seat_id=reservation_request.get("seat_id"),
            status="PENDING"
        )
        db.add(new_attempt)
        db.commit()
        db.refresh(new_attempt)
        logger.info(f"Reservation attempt {reservation_attempt_id} saved to DB.")

        # Prepare the event data
        event_data = {
            "reservation_attempt_id": reservation_attempt_id,
            "user_id": reservation_request.get("user_id"),
            "event_id": reservation_request.get("event_id"),
            "requested_seat_id": reservation_request.get("seat_id"),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        # 'reservation_attempts' 토픽으로 메시지 전송
        await producer.send_and_wait('reservation_attempts', value=event_data)
        logger.info(f"Reservation attempt {reservation_attempt_id} sent to Kafka.")

        return {
            "status": "success",
            "message": "Reservation request received and is being processed.",
            "reservation_attempt_id": reservation_attempt_id
        }
    except Exception as e:
        db.rollback() # Rollback in case of error
        logger.error(f"Failed to process reservation request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process reservation request: {e}")

@app.get("/")
def health_check():
    return {"status": "ok"}