from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.core.database import Base

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    designation = Column(String, nullable=False)
    dept = Column(String, nullable=False)
    joining_year = Column(Integer, nullable=False)
    mobile_no = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=False)
    neura_teacher_id = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    profile_image = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)