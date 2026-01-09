from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.core.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=True)
    roll_no = Column(String, unique=True, nullable=True)
    dept = Column(String, nullable=True)
    section = Column(String, nullable=True)
    series = Column(String, nullable=True)
    mobile_no = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=True)
    neura_id = Column(String, unique=True, nullable=True)
    password = Column(String, nullable=True)
    profile_image = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
