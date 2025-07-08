from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# ===============================
# Event Schemas
# ===============================

class EventBase(BaseModel):
    name: str
    description: Optional[str] = None
    event_date: datetime
    total_seats: int

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    event_date: Optional[datetime] = None
    total_seats: Optional[int] = None

class Event(EventBase):
    id: int
    available_seats: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ===============================
# Seat Schemas
# ===============================

class SeatBase(BaseModel):
    event_id: int
    seat_number: str

class SeatCreate(SeatBase):
    pass

class SeatUpdate(BaseModel):
    is_reserved: bool

class Seat(SeatBase):
    id: int
    is_reserved: bool

    class Config:
        from_attributes = True