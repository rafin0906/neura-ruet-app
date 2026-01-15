from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.student_models import Student


class CR(Student):
    __tablename__ = "cr"

    id = Column(Integer, ForeignKey("students.id"), primary_key=True)
    cr_no = Column(String, unique=True, nullable=True)
    neura_cr_id = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student", backref="cr")
