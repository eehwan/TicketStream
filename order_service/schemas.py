from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class OrderBase(BaseModel):
    reservation_attempt_id: str
    user_id: int
    event_id: int
    seat_id: str

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    status: str

class Order(OrderBase):
    id: int
    order_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
