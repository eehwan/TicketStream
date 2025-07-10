from sqlalchemy.orm import Session
from reservation_api.models import ReservationAttempt
from reservation_api.schemas import ReservationAttemptCreate

def create_reservation_attempt(db: Session, reservation_attempt: ReservationAttemptCreate, reservation_attempt_id: str):
    db_reservation_attempt = ReservationAttempt(
        reservation_attempt_id=reservation_attempt_id,
        user_id=reservation_attempt.user_id,
        event_id=reservation_attempt.event_id,
        requested_seat_id=reservation_attempt.requested_seat_id,
        status="PENDING"
    )
    db.add(db_reservation_attempt)
    db.commit()
    db.refresh(db_reservation_attempt)
    return db_reservation_attempt
