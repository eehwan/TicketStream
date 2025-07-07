from sqlalchemy.orm import Session
from event_api.models import Event, Seat
from event_api.schemas import EventCreate, SeatCreate

def create_event(db: Session, event: EventCreate):
    db_event = Event(**event.model_dump(), available_seats=event.total_seats)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

def get_event(db: Session, event_id: int):
    return db.query(Event).filter(Event.id == event_id).first()

def get_events(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Event).offset(skip).limit(limit).all()

def update_event(db: Session, event_id: int, event_data: dict):
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if db_event:
        for key, value in event_data.items():
            setattr(db_event, key, value)
        db.commit()
        db.refresh(db_event)
    return db_event

def delete_event(db: Session, event_id: int):
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if db_event:
        db.delete(db_event)
        db.commit()
    return db_event

def create_seat(db: Session, seat: SeatCreate):
    db_seat = Seat(**seat.model_dump())
    db.add(db_seat)
    db.commit()
    db.refresh(db_seat)
    return db_seat

def get_seats_by_event(db: Session, event_id: int):
    return db.query(Seat).filter(Seat.event_id == event_id).all()

def get_seat(db: Session, seat_id: int):
    return db.query(Seat).filter(Seat.id == seat_id).first()

def update_seat_reservation_status(db: Session, seat_id: int, is_reserved: bool):
    db_seat = db.query(Seat).filter(Seat.id == seat_id).first()
    if db_seat:
        db_seat.is_reserved = is_reserved
        db.commit()
        db.refresh(db_seat)
    return db_seat
