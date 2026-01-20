import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.db.database import Base


class LectureSlide(Base):
    __tablename__ = "lecture_slides"

    id = Column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    drive_url = Column(String, nullable=False)

    course_code = Column(String, nullable=False)
    course_name = Column(String, nullable=False)
    topic = Column(String, nullable=False)

    dept = Column(String, nullable=False)
    sec = Column(String, nullable=False)
    series = Column(String, nullable=False)

    uploaded_by_cr_id = Column(
        String(36),
        ForeignKey("crs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    uploaded_by_cr = relationship(
        "CR",
        foreign_keys=[uploaded_by_cr_id],
        passive_deletes=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_lecture_slides_uploaded_by_cr_id", "uploaded_by_cr_id"),
        Index("ix_lecture_slides_course_code", "course_code"),
        Index("ix_lecture_slides_dept_sec_series", "dept", "sec", "series"),
    )
