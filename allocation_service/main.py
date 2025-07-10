import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
import redis.asyncio as redis

import json
import os

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka 및 Redis 설정
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
SEAT_ALLOCATION_TTL_SECONDS = 5 * 60  # 5분

# Kafka 토픽 이름
RESERVATION_ATTEMPTS_TOPIC = "reservation_attempts"
PAYMENT_EVENTS_TOPIC = "payment_events"
SEAT_ALLOCATIONS_TOPIC = "seat_allocations"

# 전역 변수
consumer: AIOKafkaConsumer = None
producer: AIOKafkaProducer = None
redis_client: redis.Redis = None
consumer_task: asyncio.Task = None
redis_pubsub_task: asyncio.Task = None

async def release_seat(event_id: int, seat_id: str, reason: str):
    """Redis에서 좌석을 해제하고 SeatReleased 이벤트를 발행합니다."""
    redis_key = f"allocated_seat:{event_id}:{seat_id}"
    # 키를 삭제하여 좌석 해제
    deleted_count = await redis_client.delete(redis_key)
    if deleted_count > 0:
        logger.info(f"Seat {seat_id} for event {event_id} released from Redis.")
        # SeatReleased 이벤트 발행
        await producer.send_and_wait(
            SEAT_ALLOCATIONS_TOPIC,
            value={
                "event_type": "SeatReleased",
                "event_id": event_id,
                "seat_id": seat_id,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )
    else:
        logger.warning(f"Attempted to release seat {seat_id} for event {event_id}, but it was not found in Redis.")

async def consume_redis_keyspace_events():
    """Redis Keyspace Notifications를 소비하여 만료된 좌석을 처리합니다."""
    logger.info("Starting Redis Keyspace Notifications consumer loop...")
    pubsub = redis_client.pubsub()
    # 'expired' 이벤트만 구독하여 관련 없는 이벤트를 필터링합니다.
    await pubsub.psubscribe(f"__keyspace@0__:*expired")

    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                key = message["data"].decode('utf-8')
                if key.startswith("allocated_seat:"):
                    logger.info(f"Redis key expired: {key}")
                    parts = key.split(":")
                    if len(parts) == 3:
                        event_id, seat_id = int(parts[1]), parts[2]
                        # 만료된 좌석 해제
                        await release_seat(event_id, seat_id, reason="Expired")
    except asyncio.CancelledError:
        logger.info("Redis pub/sub task cancelled.")
    except Exception as e:
        logger.error(f"Error in Redis pub/sub loop: {e}")
    finally:
        if pubsub:
            await pubsub.close()

async def handle_reservation_attempt(event_data: dict):
    """예약 시도 이벤트를 처리합니다."""
    redis_key = f"allocated_seat:{event_data['event_id']}:{event_data['requested_seat_id']}"
    allocation_data = {
        "reservation_attempt_id": event_data['reservation_attempt_id'],
        "user_id": event_data['user_id'],
        "allocated_at": datetime.utcnow().isoformat() + "Z"
    }
    
    # SETNX를 사용하여 원자적으로 좌석 할당 시도
    if await redis_client.setnx(redis_key, json.dumps(allocation_data)):
        await redis_client.expire(redis_key, SEAT_ALLOCATION_TTL_SECONDS)
        logger.info(f"Seat {event_data['requested_seat_id']} allocated successfully.")
        # SeatAllocated 이벤트 발행
        await producer.send_and_wait(
            SEAT_ALLOCATIONS_TOPIC,
            value={
                "event_type": "SeatAllocated",
                "reservation_attempt_id": event_data['reservation_attempt_id'],
                "user_id": event_data['user_id'],
                "event_id": event_data['event_id'],
                "seat_id": event_data['requested_seat_id'],
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )
    else:
        logger.warning(f"Seat {event_data['requested_seat_id']} already allocated.")
        # SeatAllocationFailed 이벤트 발행 (이미 좌석이 할당됨)
        await producer.send_and_wait(
            SEAT_ALLOCATIONS_TOPIC,
            value={
                "event_type": "SeatAllocationFailed",
                "reservation_attempt_id": event_data['reservation_attempt_id'],
                "user_id": event_data['user_id'],
                "event_id": event_data['event_id'],
                "seat_id": event_data['requested_seat_id'],
                "reason": "AlreadyAllocated",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )

async def handle_payment_event(event_data: dict):
    """결제 관련 이벤트를 처리합니다."""
    event_type = event_data.get("event_type")
    event_id = event_data.get("event_id")
    seat_id = event_data.get("seat_id")
    redis_key = f"allocated_seat:{event_id}:{seat_id}"

    if event_type == "PaymentSuccessful":
        # 결제가 성공하면 좌석의 TTL을 제거하여 영구적으로 만듭니다.
        if await redis_client.persist(redis_key):
            logger.info(f"Payment successful for seat {seat_id}. TTL removed.")
        else:
            logger.warning(f"Payment successful for seat {seat_id}, but seat was not found in Redis (may have expired).")
    
    elif event_type == "PaymentFailed":
        logger.warning(f"Payment failed for seat {seat_id}. Releasing seat.")
        # 결제가 실패하면 좌석을 즉시 해제합니다.
        await release_seat(event_id, seat_id, reason="PaymentFailed")

async def consume_kafka_messages():
    """모든 관련 Kafka 토픽의 메시지를 소비하고 처리합니다."""
    logger.info("Starting Kafka consumer loop...")
    try:
        async for msg in consumer:
            logger.info(f"Received message from topic {msg.topic}: {msg.value}")
            try:
                if msg.topic == RESERVATION_ATTEMPTS_TOPIC:
                    await handle_reservation_attempt(msg.value)
                elif msg.topic == PAYMENT_EVENTS_TOPIC:
                    await handle_payment_event(msg.value)
            except Exception as e:
                logger.error(f"Error processing message: {msg.value}, error: {e}")
    except asyncio.CancelledError:
        logger.info("Kafka consumer task cancelled.")
    finally:
        if consumer:
            await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer, producer, redis_client, consumer_task, redis_pubsub_task
    loop = asyncio.get_event_loop()

    # Redis 및 Kafka 클라이언트 초기화
    while True:
        try:
            logger.info("Attempting to connect to Redis and Kafka...")
            redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
            await redis_client.ping()
            
            # Redis Keyspace Notifications 활성화
            await redis_client.config_set("notify-keyspace-events", "Ex")
            
            consumer = AIOKafkaConsumer(
                RESERVATION_ATTEMPTS_TOPIC, PAYMENT_EVENTS_TOPIC, # 여러 토픽 구독
                loop=loop, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                auto_offset_reset='earliest', group_id='allocation-service-group',
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            producer = AIOKafkaProducer(
                loop=loop, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await redis_client.ping()
            await consumer.start()
            await producer.start()
            logger.info("Redis and Kafka clients connected successfully!")
            break
        except Exception as e:
            logger.error(f"Connection failed: {e}. Retrying in 5 seconds...")
            if consumer: await consumer.stop()
            if producer: await producer.stop()
            if redis_client: await redis_client.close()
            await asyncio.sleep(5)

    consumer_task = asyncio.create_task(consume_kafka_messages())
    redis_pubsub_task = asyncio.create_task(consume_redis_keyspace_events())
    yield
    
    # 애플리케이션 종료 시 리소스 정리
    tasks = [consumer_task, redis_pubsub_task]
    for task in tasks:
        if task and not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    if producer: await producer.stop()
    if consumer: await consumer.stop()
    if redis_client: await redis_client.close()
    logger.info("Allocation service shut down gracefully.")

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Allocation service is running."}
