from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.db.database import Base

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    dept = Column(String, nullable=True)
    joining_year = Column(Integer, nullable=True)
    mobile_no = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, nullable=True)
    neura_teacher_id = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    setup_token = Column(String, unique=True, nullable=True)

    # ✅ refresh token system (production-ready)
    refresh_token_id = Column(String, unique=True, nullable=True)
    refresh_token_hash = Column(String, nullable=True)
    refresh_token_expires_at = Column(DateTime, nullable=True)
    # JWT invalidation / global logout
    token_version = Column(Integer, default=1)

    profile_image = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
