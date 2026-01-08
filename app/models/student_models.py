from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.core.database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    roll_no = Column(String, unique=True, nullable=False)
    dept = Column(String, nullable=False)
    section = Column(String, nullable=True)
    series = Column(String, nullable=True)
    mobile_no = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=False)
    neura_id = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    profile_image = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)