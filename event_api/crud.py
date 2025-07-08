from sqlalchemy.orm import Session
from event_api import models, schemas

# ===============================
# Event CRUD
# ===============================

def get_event(db: Session, event_id: int):
    return db.query(models.Event).filter(models.Event.id == event_id).first()

def get_events(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Event).offset(skip).limit(limit).all()

def create_event(db: Session, event: schemas.EventCreate):
    db_event = models.Event(**event.model_dump(), available_seats=event.total_seats)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

def update_event(db: Session, event_id: int, event_update: schemas.EventUpdate):
    db_event = get_event(db, event_id)
    if db_event:
        update_data = event_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_event, key, value)
        db.commit()
        db.refresh(db_event)
    return db_event

def delete_event(db: Session, event_id: int):
    db_event = get_event(db, event_id)
    if db_event:
        db.delete(db_event)
        db.commit()
    return db_event

# ===============================
# Seat CRUD
# ===============================

def get_seat(db: Session, seat_id: int):
    return db.query(models.Seat).filter(models.Seat.id == seat_id).first()

def get_seats_by_event(db: Session, event_id: int):
    return db.query(models.Seat).filter(models.Seat.event_id == event_id).all()

def create_seat(db: Session, seat: schemas.SeatCreate):
    db_seat = models.Seat(**seat.model_dump())
    db.add(db_seat)
    db.commit()
    db.refresh(db_seat)
    return db_seat

def update_seat(db: Session, seat_id: int, seat_update: schemas.SeatUpdate):
    db_seat = get_seat(db, seat_id)
    if db_seat:
        update_data = seat_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_seat, key, value)
        db.commit()
        db.refresh(db_seat)
    return db_seat