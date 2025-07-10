
import asyncio
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Depends
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from sqlalchemy.orm import Session

import json
import os

from order_service.database import Base, engine, get_db
from order_service import crud, schemas

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka 설정
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
SEAT_ALLOCATIONS_TOPIC = "seat_allocations"
PAYMENT_EVENTS_TOPIC = "payment_events" # 새로운 토픽

consumer: AIOKafkaConsumer = None
producer: AIOKafkaProducer = None
consumer_task: asyncio.Task = None

async def send_payment_event(event_data: dict):
    """결제 관련 이벤트를 Kafka에 전송합니다."""
    try:
        await producer.send_and_wait(
            PAYMENT_EVENTS_TOPIC,
            json.dumps(event_data).encode('utf-8')
        )
        logger.info(f"Event {event_data['event_type']} for order {event_data['order_id']} sent to Kafka.")
    except Exception as e:
        logger.error(f"Failed to send event for order {event_data['order_id']} to Kafka: {e}")

async def consume_messages():
    """Kafka로부터 메시지를 지속적으로 소비하여 처리합니다."""
    logger.info("Starting Kafka consumer loop...")
    try:
        async for message in consumer:
            logger.info(f"Received raw message: {message}")
            try:
                event_data = message.value
                logger.info(f"Successfully deserialized event: {event_data}")

                if event_data.get("event_type") == "SeatAllocated":
                    db = next(get_db())
                    try:
                        # Create order using CRUD function
                        order_create_data = schemas.OrderCreate(
                            reservation_attempt_id=event_data.get("reservation_attempt_id"),
                            user_id=event_data.get("user_id"),
                            event_id=event_data.get("event_id"),
                            seat_id=event_data.get("seat_id")
                        )
                        new_order = crud.create_order(db, order_create_data)
                        logger.info(f"Order {new_order.order_id} created with PENDING status.")

                        # --- 2. 모의 결제 처리 ---
                        await asyncio.sleep(2)  # Simulate payment processing time
                        payment_successful = random.random() < 0.9  # 90% success rate

                        payment_event = {
                            "order_id": new_order.order_id,
                            "reservation_attempt_id": new_order.reservation_attempt_id,
                            "user_id": new_order.user_id,
                            "event_id": new_order.event_id,
                            "seat_id": new_order.seat_id,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }

                        if payment_successful:
                            crud.update_order_status(db, new_order.order_id, "COMPLETED")
                            payment_event["event_type"] = "PaymentSuccessful"
                            logger.info(f"Mock payment SUCCEEDED for order {new_order.order_id}.")
                        else:
                            crud.update_order_status(db, new_order.order_id, "FAILED")
                            payment_event["event_type"] = "PaymentFailed"
                            logger.error(f"Mock payment FAILED for order {new_order.order_id}.")
                        
                        # --- 3. 결제 결과 이벤트 발행 ---
                        await send_payment_event(payment_event)

                    except Exception as db_e:
                        db.rollback()
                        logger.error(f"Error processing order: {db_e}")
                    finally:
                        db.close()

            except Exception as e:
                logger.error(f"Error processing message: {message.value}, error: {e}")
    except asyncio.CancelledError:
        logger.info("Consumer task cancelled.")
    finally:
        if consumer:
            await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer, producer, consumer_task
    loop = asyncio.get_event_loop()

    # Kafka Consumer 및 Producer 초기화
    while True:
        try:
            logger.info("Attempting to connect to Kafka...")
            consumer = AIOKafkaConsumer(
                SEAT_ALLOCATIONS_TOPIC,
                loop=loop,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                auto_offset_reset='earliest',
                group_id='order-processing-group',
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            producer = AIOKafkaProducer(
                loop=loop,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS
            )
            await consumer.start()
            await producer.start()
            logger.info("Kafka Consumer and Producer connected successfully!")
            break
        except KafkaConnectionError as e:
            logger.error(f"Kafka not available: {e}. Retrying in 5 seconds...")
            if consumer: await consumer.stop()
            if producer: await producer.stop()
            await asyncio.sleep(5)

    # 데이터베이스 테이블 생성
    try:
        logger.info("Creating database tables for Order Service...")
        Base.metadata.create_all(bind=engine)
        logger.info("Order Service database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating Order Service database tables: {e}")

    consumer_task = asyncio.create_task(consume_messages())
    yield
    
    # 애플리케이션 종료 시 리소스 정리
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    if consumer:
        await consumer.stop()
    if producer:
        await producer.stop()
    logger.info("Order service shut down gracefully.")

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Order service is running."}
