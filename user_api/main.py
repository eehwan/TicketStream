import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from user_api.database import Base, engine
from user_api.routers import users
from common.tracing import setup_telemetry # common 모듈 임포트

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Setting up OpenTelemetry...")
    setup_telemetry(app) # 공통 함수 호출
    logger.info("OpenTelemetry setup complete.")

    logger.info("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(users.router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "User service is running."}
