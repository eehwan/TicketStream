import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
import json

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

consumer: AIOKafkaConsumer = None
consumer_task: asyncio.Task = None

async def consume_messages():
    """Kafka로부터 메시지를 지속적으로 소비하여 처리합니다."""
    logger.info("Starting Kafka consumer loop...")
    try:
        async for message in consumer:
            logger.info(f"Received raw message: {message}")
            try:
                reservation_details = message.value
                logger.info(f"Successfully deserialized reservation: {reservation_details}")
                # 여기에 실제 주문 처리 로직이 들어갑니다.
                # (예: 데이터베이스에 저장, 결제 처리, 이메일 발송 등)
                # 지금은 단순히 로그만 남깁니다.
                logger.info(f"Processing order for user {reservation_details.get('user_email')} for event {reservation_details.get('event_id')}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message value: {message.value}, error: {e}")
            except Exception as e:
                logger.error(f"Error processing message: {message.value}, error: {e}")
    except asyncio.CancelledError:
        logger.info("Consumer task cancelled.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in consumer loop: {e}")
    finally:
        logger.info("Stopping consumer...")
        if consumer:
            await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer, consumer_task
    logger.info("Attempting to connect to Kafka consumer...")
    loop = asyncio.get_event_loop()
    while True:
        try:
            consumer = AIOKafkaConsumer(
                'reservation-topic',
                loop=loop,
                bootstrap_servers='kafka:9092',
                auto_offset_reset='earliest', # 가장 처음부터 메시지를 가져옴
                group_id='order-processing-group', # 컨슈머 그룹 ID
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            await consumer.start()
            logger.info("Kafka Consumer connected successfully!")
            break
        except KafkaConnectionError as e:
            logger.error(f"Kafka broker not available for consumer: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred during Kafka consumer initialization: {e}. Retrying in 5 seconds...")
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

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Order processing service is running."}