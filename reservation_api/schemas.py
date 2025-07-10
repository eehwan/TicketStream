from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReservationAttemptBase(BaseModel):
    user_id: int
    event_id: int
    requested_seat_id: str

class ReservationAttemptCreate(ReservationAttemptBase):
    pass

class ReservationAttempt(ReservationAttemptBase):
    id: int
    reservation_attempt_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
