import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from event_api.database import Base, engine, SessionLocal
from event_api.routers import events
from event_api import crud
from common.tracing import setup_telemetry # common 모듈 임포트

import json

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

consumer: AIOKafkaConsumer = None
consumer_task: asyncio.Task = None

async def consume_messages():
    logger.info("Starting Kafka consumer loop for Event API...")
    try:
        async for message in consumer:
            logger.info(f"Received raw message in Event API: {message}")
            try:
                event_data = message.value
                logger.info(f"Successfully deserialized event in Event API: {event_data}")
                
                event_type = event_data.get("event_type")
                seat_id = event_data.get("seat_id")
                event_id = event_data.get("event_id")
                
                if not all([seat_id, event_id]):
                    logger.error(f"Missing required fields in event: {event_data}")
                    continue

                db = SessionLocal()
                try:
                    if event_type == "SeatAllocated":
                        logger.info(f"Processing SeatAllocated event for seat_id: {seat_id}, event_id: {event_id}")
                        crud.update_seat_reservation_status(db, seat_number=seat_id, event_id=event_id, is_reserved=True)
                        logger.info(f"Seat {seat_id} for event {event_id} marked as reserved in Event DB.")
                    elif event_type == "SeatAllocationFailed":
                        logger.info(f"Processing SeatAllocationFailed event for seat_id: {seat_id}, event_id: {event_id}. No state change in Event DB as seat was not allocated by this attempt.")
                    elif event_type == "SeatReleased":
                        logger.info(f"Processing SeatReleased event for seat_id: {seat_id}, event_id: {event_id}")
                        crud.update_seat_reservation_status(db, seat_number=seat_id, event_id=event_id, is_reserved=False)
                        logger.info(f"Seat {seat_id} for event {event_id} marked as available in Event DB due to release.")
                    else:
                        logger.warning(f"Unhandled event type received in Event API: {event_type}")
                except Exception as db_e:
                    db.rollback()
                    logger.error(f"Error updating seat status in Event DB for seat {seat_id}: {db_e}")
                finally:
                    db.close()

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message value in Event API: {message.value}, error: {e}")
            except Exception as e:
                logger.error(f"Error processing message in Event API: {message.value}, error: {e}")
    except asyncio.CancelledError:
        logger.info("Event API consumer task cancelled.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in Event API consumer loop: {e}")
    finally:
        logger.info("Stopping Event API consumer...")
        if consumer:
            await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Setting up OpenTelemetry...")
    setup_telemetry(app) # 공통 함수 호출
    logger.info("OpenTelemetry setup complete.")

    global consumer, consumer_task
    logger.info("Creating database tables for Event Service...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Event Service database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating Event Service database tables: {e}")

    logger.info("Attempting to connect to Kafka consumer for Event API...")
    loop = asyncio.get_event_loop()
    while True:
        try:
            consumer = AIOKafkaConsumer(
                'seat_allocations',
                loop=loop,
                bootstrap_servers='kafka:9092',
                auto_offset_reset='earliest',
                group_id='event-api-group',
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            await consumer.start()
            logger.info("Kafka Consumer for Event API connected successfully!")
            break
        except KafkaConnectionError as e:
            logger.error(f"Kafka broker not available for Event API consumer: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred during Event API Kafka consumer initialization: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

    consumer_task = asyncio.create_task(consume_messages())
    yield
    # 애플리케이션 종료 시 컨슈머 중지
    if consumer_task:
        consumer_task.cancel()
        await consumer_task
    if consumer:
        await consumer.stop()

app = FastAPI(lifespan=lifespan)

app.include_router(events.router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Event service is running."}