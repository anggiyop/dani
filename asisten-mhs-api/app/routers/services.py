from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/v1", tags=["Helpdesk"])

@router.get("/services", response_model=List[schemas.ServiceOut])
def list_services(db: Session = Depends(get_db)):
    return db.query(models.Service).filter(models.Service.is_active == True).all()

@router.post("/services", response_model=schemas.ServiceOut)
def create_service(payload: schemas.ServiceBase, db: Session = Depends(get_db)):
    svc = models.Service(**payload.model_dump())
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc
