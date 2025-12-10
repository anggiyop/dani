from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date, timedelta
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/v1", tags=["Tiket"])

@router.post("/tickets", response_model=schemas.TicketOut)
def create_ticket(payload: schemas.TicketCreate, db: Session = Depends(get_db)):
    service = db.query(models.Service).get(payload.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    ticket = models.Ticket(
        student_npm=payload.student_npm,
        service_id=payload.service_id,
        attachments=payload.attachments,
        note=payload.note,
        due_date=date.today() + timedelta(days=service.sla_days or 0)
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket
