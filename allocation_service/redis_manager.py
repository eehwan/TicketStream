import asyncio
import logging
import redis.asyncio as redis
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
SEAT_ALLOCATION_TTL_SECONDS = 5 * 60  # 5분

redis_client: redis.Redis = None

async def init_redis_client():
    global redis_client
    logger.info(f"Attempting to connect to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    while True:
        try:
            redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
            await redis_client.ping()
            # Redis Keyspace Notifications 활성화
            await redis_client.config_set("notify-keyspace-events", "Ex")
            logger.info("Redis connected successfully!")
            break
        except Exception as e:
            logger.error(f"Redis not available: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

async def close_redis_client():
    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed.")

async def release_seat(producer, SEAT_ALLOCATIONS_TOPIC, event_id: int, seat_id: str, reason: str):
    """Redis에서 좌석을 해제하고 SeatReleased 이벤트를 발행합니다."""
    redis_key = f"allocated_seat:{event_id}:{seat_id}"
    deleted_count = await redis_client.delete(redis_key)
    if deleted_count > 0:
        logger.info(f"Seat {seat_id} for event {event_id} released from Redis.")
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

async def handle_reservation_attempt(producer, SEAT_ALLOCATIONS_TOPIC, event_data: dict):
    """예약 시도 이벤트를 처리합니다."""
    redis_key = f"allocated_seat:{event_data['event_id']}:{event_data['requested_seat_id']}"
    allocation_data = {
        "reservation_attempt_id": event_data['reservation_attempt_id'],
        "user_id": event_data['user_id'],
        "allocated_at": datetime.utcnow().isoformat() + "Z"
    }
    
    if await redis_client.setnx(redis_key, json.dumps(allocation_data)):
        await redis_client.expire(redis_key, SEAT_ALLOCATION_TTL_SECONDS)
        logger.info(f"Seat {event_data['requested_seat_id']} allocated successfully.")
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

async def handle_payment_event(producer, SEAT_ALLOCATIONS_TOPIC, event_data: dict):
    """결제 관련 이벤트를 처리합니다."""
    event_type = event_data.get("event_type")
    event_id = event_data.get("event_id")
    seat_id = event_data.get("seat_id")
    redis_key = f"allocated_seat:{event_id}:{seat_id}"

    if event_type == "PaymentSuccessful":
        if await redis_client.persist(redis_key):
            logger.info(f"Payment successful for seat {seat_id}. TTL removed.")
        else:
            logger.warning(f"Payment successful for seat {seat_id}, but seat was not found in Redis (may have expired).")
    
    elif event_type == "PaymentFailed":
        logger.warning(f"Payment failed for seat {seat_id}. Releasing seat.")
        await release_seat(producer, SEAT_ALLOCATIONS_TOPIC, event_id, seat_id, reason="PaymentFailed")

async def consume_redis_keyspace_events(producer, SEAT_ALLOCATIONS_TOPIC):
    """Redis Keyspace Notifications를 소비하여 만료된 좌석을 처리합니다."""
    logger.info("Starting Redis Keyspace Notifications consumer loop...")
    pubsub = redis_client.pubsub()
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
                        await release_seat(producer, SEAT_ALLOCATIONS_TOPIC, event_id, seat_id, reason="Expired")
    except asyncio.CancelledError:
        logger.info("Redis pub/sub task cancelled.")
    except Exception as e:
        logger.error(f"Error in Redis pub/sub loop: {e}")
    finally:
        if pubsub:
            await pubsub.close()
