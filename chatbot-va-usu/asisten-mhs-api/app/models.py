import uuid
from sqlalchemy import (
    Column, String, Integer, Boolean, Date, Time, ForeignKey, JSON, text
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from .database import Base

class Student(Base):
    __tablename__ = "students"
    npm = Column(String(20), primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True)
    fakultas = Column(String(120))
    prodi = Column(String(120))
    angkatan = Column(Integer)

class Lecturer(Base):
    __tablename__ = "lecturers"
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(120), nullable=False)
    email = Column(String(120))

class Course(Base):
    __tablename__ = "courses"
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(160), nullable=False)
    sks = Column(Integer, nullable=False)

class Class(Base):
    __tablename__ = "classes"
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = Column(CHAR(36), ForeignKey("courses.id"))
    lecturer_id = Column(CHAR(36), ForeignKey("lecturers.id"))
    term_code = Column(String(20))
    day = Column(String(10))
    start_time = Column(Time)
    end_time = Column(Time)
    room = Column(String(60))

    course = relationship("Course")
    lecturer = relationship("Lecturer")

class Service(Base):
    __tablename__ = "services"
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(160))
    description = Column(String)
    unit_owner = Column(String(100))
    sla_days = Column(Integer)
    fee_rp = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    sop_ref = Column(String(200))

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_npm = Column(String(20), ForeignKey("students.npm"))
    service_id = Column(CHAR(36), ForeignKey("services.id"))
    status = Column(String(20), default="submitted")
    attachments = Column(JSON)
    note = Column(String(255))
    due_date = Column(Date)
