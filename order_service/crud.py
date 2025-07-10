from sqlalchemy.orm import Session
from order_service.models import Order
from order_service.schemas import OrderCreate, OrderUpdate
from uuid import uuid4

def create_order(db: Session, order: OrderCreate):
    db_order = Order(
        order_id=str(uuid4()),
        reservation_attempt_id=order.reservation_attempt_id,
        user_id=order.user_id,
        event_id=order.event_id,
        seat_id=order.seat_id,
        status="PENDING"
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

def update_order_status(db: Session, order_id: str, status: str):
    db_order = db.query(Order).filter(Order.order_id == order_id).first()
    if db_order:
        db_order.status = status
        db.commit()
        db.refresh(db_order)
    return db_order
