from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.db.database import Base


class CR(Base):
    __tablename__ = "crs"  # choose "crs" or "cr" (but "crs" is nicer)

    id = Column(Integer, primary_key=True, index=True)

    # --- student-like profile fields ---
    full_name = Column(String, nullable=True)
    roll_no = Column(String, unique=True, nullable=False)
    dept = Column(String, nullable=True)
    section = Column(String, nullable=True)
    series = Column(String, nullable=True)
    mobile_no = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, nullable=True)
    cr_no = Column(String, nullable=True)

    # --- CR identity fields (replace neura_id) ---
    neura_cr_id = Column(String, unique=True, nullable=False)

    # --- auth ---
    password = Column(String, nullable=False)
    setup_token = Column(String, unique=True, nullable=True)

    # refresh token system
    refresh_token_id = Column(String, unique=True, nullable=True)
    refresh_token_hash = Column(String, nullable=True)
    refresh_token_expires_at = Column(DateTime, nullable=True)

    # JWT invalidation / global logout
    token_version = Column(Integer, default=1)

    profile_image = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

