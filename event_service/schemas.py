from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class EventBase(BaseModel):
    name: str
    description: Optional[str] = None
    event_date: datetime
    total_seats: int

class EventCreate(EventBase):
    pass

class EventSchema(EventBase):
    id: int
    available_seats: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SeatBase(BaseModel):
    event_id: int
    seat_number: str

class SeatCreate(SeatBase):
    pass

class SeatSchema(SeatBase):
    id: int
    is_reserved: bool

    class Config:
        from_attributes = True
