
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
import json

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

consumer: KafkaConsumer = None

async def consume_messages():
    """Kafka로부터 메시지를 지속적으로 소비하여 처리합니다."""
    logger.info("Starting Kafka consumer loop...")
    while True:
        try:
            for message in consumer:
                logger.info(f"Received raw message: {message}")
                logger.info(f"Received reservation: {message.value}")
                # 여기에 실제 주문 처리 로직이 들어갑니다.
                # (예: 데이터베이스에 저장, 결제 처리 등)
        except Exception as e:
            logger.error(f"Error consuming messages: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # global consumer
    logger.info("Attempting to connect to Kafka consumer...")
    # try:
    #     consumer = KafkaConsumer(
    #         'reservation-topic',
    #         bootstrap_servers=['kafka:9092'],
    #         auto_offset_reset='earliest', # 가장 처음부터 메시지를 가져옴
    #         group_id='order-processing-group', # 컨슈머 그룹 ID
    #         value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    #     )
    #     logger.info("Kafka Consumer connected successfully!")
    # except NoBrokersAvailable as e:
    #     logger.error(f"Kafka broker not available for consumer: {e}. Proceeding without Kafka connection.")
    # except Exception as e:
    #     logger.error(f"An unexpected error occurred during Kafka consumer initialization: {e}. Proceeding without Kafka connection.")
    # asyncio.create_task(consume_messages())
    yield
    # if consumer:
    #     consumer.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Order processing service is running."}



