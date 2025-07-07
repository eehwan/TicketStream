from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from event_api.schemas import EventCreate, EventSchema, SeatCreate, SeatSchema
from event_api.crud import (
    create_event, get_event, get_events, update_event, delete_event,
    create_seat, get_seats_by_event, get_seat, update_seat_reservation_status
)
from event_api.database import get_db

router = APIRouter()

@router.post("/events/", response_model=EventSchema, status_code=status.HTTP_201_CREATED)
def create_new_event(event: EventCreate, db: Session = Depends(get_db)):
    return create_event(db=db, event=event)

@router.get("/events/", response_model=List[EventSchema])
def read_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    events = get_events(db, skip=skip, limit=limit)
    return events

@router.get("/events/{event_id}", response_model=EventSchema)
def read_event(event_id: int, db: Session = Depends(get_db)):
    db_event = get_event(db, event_id=event_id)
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event

@router.put("/events/{event_id}", response_model=EventSchema)
def update_existing_event(event_id: int, event: EventCreate, db: Session = Depends(get_db)):
    db_event = update_event(db, event_id=event_id, event_data=event.model_dump(exclude_unset=True))
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event

@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_event(event_id: int, db: Session = Depends(get_db)):
    db_event = delete_event(db, event_id=event_id)
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"message": "Event deleted successfully"}

@router.post("/events/{event_id}/seats/", response_model=SeatSchema, status_code=status.HTTP_201_CREATED)
def create_new_seat(event_id: int, seat: SeatCreate, db: Session = Depends(get_db)):
    db_event = get_event(db, event_id=event_id)
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if seat.event_id != event_id:
        raise HTTPException(status_code=400, detail="Seat event_id does not match path event_id")
    return create_seat(db=db, seat=seat)

@router.get("/events/{event_id}/seats/", response_model=List[SeatSchema])
def read_seats_for_event(event_id: int, db: Session = Depends(get_db)):
    db_event = get_event(db, event_id=event_id)
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    seats = get_seats_by_event(db, event_id=event_id)
    return seats

@router.put("/seats/{seat_id}/reserve", response_model=SeatSchema)
def reserve_seat(seat_id: int, db: Session = Depends(get_db)):
    db_seat = update_seat_reservation_status(db, seat_id=seat_id, is_reserved=True)
    if db_seat is None:
        raise HTTPException(status_code=404, detail="Seat not found")
    if db_seat.is_reserved:
        raise HTTPException(status_code=400, detail="Seat already reserved")
    return db_seat

@router.put("/seats/{seat_id}/unreserve", response_model=SeatSchema)
def unreserve_seat(seat_id: int, db: Session = Depends(get_db)):
    db_seat = update_seat_reservation_status(db, seat_id=seat_id, is_reserved=False)
    if db_seat is None:
        raise HTTPException(status_code=404, detail="Seat not found")
    if not db_seat.is_reserved:
        raise HTTPException(status_code=400, detail="Seat is not reserved")
    return db_seat
