from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from event_api import crud, schemas
from event_api.database import get_db

router = APIRouter(
    prefix="/api/events",
    tags=["events"],
)

# ===============================
# Event Endpoints
# ===============================

@router.post("/", response_model=schemas.Event, status_code=status.HTTP_201_CREATED)
def create_event(event: schemas.EventCreate, db: Session = Depends(get_db)):
    return crud.create_event(db=db, event=event)

@router.get("/", response_model=List[schemas.Event])
def read_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_events(db, skip=skip, limit=limit)

@router.get("/{event_id}", response_model=schemas.Event)
def read_event(event_id: int, db: Session = Depends(get_db)):
    db_event = crud.get_event(db, event_id=event_id)
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event

@router.put("/{event_id}", response_model=schemas.Event)
def update_event(event_id: int, event: schemas.EventUpdate, db: Session = Depends(get_db)):
    db_event = crud.update_event(db, event_id=event_id, event_update=event)
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    db_event = crud.delete_event(db, event_id=event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    return

# ===============================
# Seat Endpoints
# ===============================

@router.post("/{event_id}/seats/", response_model=schemas.Seat, status_code=status.HTTP_201_CREATED)
def create_seat_for_event(event_id: int, seat: schemas.SeatCreate, db: Session = Depends(get_db)):
    db_event = crud.get_event(db, event_id=event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    if seat.event_id != event_id:
        raise HTTPException(status_code=400, detail="Seat event_id must match the event_id in the path")
    return crud.create_seat(db=db, seat=seat)

@router.get("/{event_id}/seats/", response_model=List[schemas.Seat])
def read_seats_for_event(event_id: int, db: Session = Depends(get_db)):
    db_event = crud.get_event(db, event_id=event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    return crud.get_seats_by_event(db, event_id=event_id)

@router.get("/{event_id}/seats/{seat_number}", response_model=schemas.Seat)
def read_seat_by_number(event_id: int, seat_number: str, db: Session = Depends(get_db)):
    db_seat = crud.get_seat_by_number_and_event(db, event_id=event_id, seat_number=seat_number)
    if not db_seat:
        raise HTTPException(status_code=404, detail="Seat not found")
    return db_seat

