from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from reservation_api.database import Base

class ReservationAttempt(Base):
    __tablename__ = "reservation_attempts"

    id = Column(Integer, primary_key=True, index=True)
    reservation_attempt_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=False)
    event_id = Column(Integer, nullable=False)
    seat_id = Column(String, nullable=False)
    status = Column(String, default="PENDING", nullable=False) # PENDING, ALLOCATED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
