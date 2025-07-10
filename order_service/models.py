from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime

from order_service.database import Base

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True, nullable=False)
    reservation_attempt_id = Column(String, nullable=False)
    user_id = Column(Integer, nullable=False)
    event_id = Column(Integer, nullable=False)
    seat_id = Column(String, nullable=False)
    status = Column(String, default="PENDING", nullable=False)  # PENDING, COMPLETED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
