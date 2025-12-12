from typing import Optional, List, Dict
from pydantic import BaseModel
from datetime import date

class ServiceBase(BaseModel):
    name: str
    description: Optional[str]
    unit_owner: Optional[str]
    sla_days: Optional[int]
    fee_rp: Optional[int]
    is_active: Optional[bool] = True
    sop_ref: Optional[str]

class ServiceOut(ServiceBase):
    id: str
    class Config: from_attributes = True

class TicketCreate(BaseModel):
    student_npm: str
    service_id: str
    attachments: Optional[Dict] = None
    note: Optional[str] = None

class TicketOut(BaseModel):
    id: str
    student_npm: str
    service_id: str
    status: str
    attachments: Optional[Dict]
    note: Optional[str]
    due_date: Optional[date]
    class Config: from_attributes = True
