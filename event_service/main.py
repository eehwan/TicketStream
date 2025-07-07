import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from event_service.database import Base, engine
from event_service.routers import events

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables for Event Service...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Event Service database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating Event Service database tables: {e}")
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(events.router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Event service is running."}
