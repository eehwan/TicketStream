import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from user_service.database import Base, engine
from user_service.routers import users

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
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