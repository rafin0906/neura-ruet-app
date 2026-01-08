from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.core.database import Base


class LectureSlide(Base):
    __tablename__ = "lecture_slides"

    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String, nullable=False)
    course_name = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    dept = Column(String, nullable=False)
    sec = Column(String, nullable=False)
    series = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
