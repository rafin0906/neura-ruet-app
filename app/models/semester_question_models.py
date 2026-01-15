import uuid
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.db.database import Base


class SemesterQuestion(Base):
    __tablename__ = "semester_questions"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    course_code = Column(String, nullable=False)
    course_name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    dept = Column(String, nullable=False)
    sec = Column(String, nullable=False)
    series = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
