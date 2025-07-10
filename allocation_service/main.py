import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

import json
import os

from allocation_service import redis_manager

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka 설정
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
RESERVATION_ATTEMPTS_TOPIC = "reservation_attempts"
PAYMENT_EVENTS_TOPIC = "payment_events"
SEAT_ALLOCATIONS_TOPIC = "seat_allocations"

# 전역 변수
consumer: AIOKafkaConsumer = None
producer: AIOKafkaProducer = None
consumer_task: asyncio.Task = None
redis_pubsub_task: asyncio.Task = None

async def consume_kafka_messages():
    """모든 관련 Kafka 토픽의 메시지를 소비하고 처리합니다."""
    logger.info("Starting Kafka consumer loop...")
    try:
        async for msg in consumer:
            logger.info(f"Received message from topic {msg.topic}: {msg.value}")
            try:
                if msg.topic == RESERVATION_ATTEMPTS_TOPIC:
                    await redis_manager.handle_reservation_attempt(producer, SEAT_ALLOCATIONS_TOPIC, msg.value)
                elif msg.topic == PAYMENT_EVENTS_TOPIC:
                    await redis_manager.handle_payment_event(producer, SEAT_ALLOCATIONS_TOPIC, msg.value)
            except Exception as e:
                logger.error(f"Error processing message: {msg.value}, error: {e}")
    except asyncio.CancelledError:
        logger.info("Kafka consumer task cancelled.")
    finally:
        if consumer:
            await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer, producer, consumer_task, redis_pubsub_task
    loop = asyncio.get_event_loop()

    # Redis 클라이언트 초기화
    await redis_manager.init_redis_client()

    # Kafka 클라이언트 초기화
    while True:
        try:
            logger.info("Attempting to connect to Kafka...")
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
            await consumer.start()
            await producer.start()
            logger.info("Kafka clients connected successfully!")
            break
        except KafkaConnectionError as e:
            logger.error(f"Kafka broker not available: {e}. Retrying in 5 seconds...")
            if consumer: await consumer.stop()
            if producer: await producer.stop()
            await asyncio.sleep(5)

    consumer_task = asyncio.create_task(consume_kafka_messages())
    redis_pubsub_task = asyncio.create_task(redis_manager.consume_redis_keyspace_events(producer, SEAT_ALLOCATIONS_TOPIC))
    yield
    
    # 애플리케이션 종료 시 리소스 정리
    tasks = [consumer_task, redis_pubsub_task]
    for task in tasks:
        if task and not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    if producer: await producer.stop()
    if consumer: await consumer.stop()
    await redis_manager.close_redis_client()
    logger.info("Allocation service shut down gracefully.")

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Allocation service is running."}
