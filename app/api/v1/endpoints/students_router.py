from fastapi import FastAPI, HTTPException, status, Response, Depends, APIRouter
from sqlalchemy.orm import Session
from app.core.database import get_db
from typing import List

import os
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta


from app.models.student_models import Student
from app.schemas.student_schemas import StudentLoginSchema, StudentSchema
from app.schemas.utils_schema import ForgetPasswordSchema
from app.schemas.utils_schema import ResetPasswordSchema
from app.utils.hashing import get_password_hash
from app.utils.logger import logger

# Temporary in-memory OTP store: { email: {otp: str, expires: datetime} }
otp_store = {}


def _mask_otp(otp: str) -> str:
    if not otp or len(otp) < 2:
        return "**"
    return "*" * (len(otp) - 1) + otp[-1]


def sanitize_otp_store() -> dict:
    """Return a sanitized copy of otp_store suitable for logging (mask OTP values)."""
    sanitized = {}
    for email, entry in otp_store.items():
        sanitized[email] = {
            "otp": _mask_otp(entry.get("otp")),
            "expires": (
                entry.get("expires").isoformat() if entry.get("expires") else None
            ),
        }
    return sanitized


def cleanup_expired_otps() -> None:
    """Remove expired OTPs from the in-memory store."""
    now = datetime.utcnow()
    expired = [
        email
        for email, e in otp_store.items()
        if e.get("expires") and e["expires"] < now
    ]
    for email in expired:
        logger.debug("Removing expired OTP for %s", email)
        del otp_store[email]


router = APIRouter(prefix="/students", tags=["Students"])


@router.post("/login")
def login(payload: StudentLoginSchema, db: Session = Depends(get_db)):
    # check duplicate
    db_student = db.query(Student).filter(Student.neura_id == payload.neura_id).first()
    if not db_student:
        raise HTTPException(400, "Neura ID invalid")

    if db_student.password != payload.password:
        raise HTTPException(400, "Password invalid")

    return {"message": "Login successful"}


@router.post("/forget-password")
def forget_password(payload: ForgetPasswordSchema, db: Session = Depends(get_db)):
    db_student = db.query(Student).filter(Student.email == payload.email).first()
    if not db_student:
        raise HTTPException(400, "Email not found")

    # cleanup expired entries and generate 4-digit OTP
    cleanup_expired_otps()
    otp = f"{random.randint(1000, 9999)}"
    expires = datetime.utcnow() + timedelta(minutes=10)
    otp_store[payload.email] = {"otp": otp, "expires": expires}
    masked = _mask_otp(otp)
    logger.info(
        "Generated OTP for %s (masked=%s), expires=%s",
        payload.email,
        masked,
        expires.isoformat(),
    )

    # compose email
    subject = "Your password reset OTP"
    body = f"Your password reset OTP is: {otp}. It will expire in 10 minutes."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMTP_FROM", "no-reply@example.com")
    msg["To"] = payload.email
    msg.set_content(body)

    smtp_host = os.getenv("SMTP_HOST")
    if smtp_host:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
                logger.info("Sent OTP email to %s", payload.email)
        except Exception as e:
            logger.exception("Failed to send OTP email")
            raise HTTPException(status_code=500, detail="Failed to send OTP email")
    else:
        # Fallback: log the OTP so developers can see it during local dev
        logger.info(
            "SMTP not configured; OTP generated for %s (masked=%s)",
            payload.email,
            _mask_otp(otp),
        )
        logger.debug("Full OTP for %s: %s", payload.email, otp)

    # logger.info("Sanitized OTP store after send: %s", sanitize_otp_store())
    # logger.info("Full OTP store after send (debug only): %s", otp_store)

    return {"message": "OTP sent to your email"}


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordSchema,
    db: Session = Depends(get_db),
):
    db_student = db.query(Student).filter(Student.email == payload.email).first()
    if not db_student:
        raise HTTPException(400, "Email not found")

    cleanup_expired_otps()
    otp_entry = otp_store.get(payload.email)

    logger.info("Email: %s", payload.email)
    logger.info("OTP entered: '%s'", payload.otp)
    logger.info("OTP stored: '%s'", otp_entry["otp"] if otp_entry else None)

    if not otp_entry or otp_entry["otp"] != payload.otp:
        raise HTTPException(400, "Invalid OTP")

    if datetime.utcnow() > otp_entry["expires"]:
        del otp_store[payload.email]
        raise HTTPException(400, "OTP expired")

    logger.info("Current OTP store: %s", sanitize_otp_store())

    # Ensure new password matches confirmation
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Confirm Password does not match")

    # Update password
    hashed_password = get_password_hash(payload.new_password)
    db_student.password = hashed_password
    db.commit()

    # Remove used OTP
    del otp_store[payload.email]

    return {"message": "Password reset successful"}


@router.post("/profile-setup")
def profile_setup(payload: StudentSchema, db: Session = Depends(get_db)):
    """Create or update student's profile based on `StudentSchema`.

    Expects `neura_id` to identify the student. Updates fields present in
    the payload and returns the updated profile.
    """
    db_student = db.query(Student).filter(Student.neura_id == payload.neura_id).first()
    if not db_student:
        raise HTTPException(status_code=400, detail="Student not found")

    # Update allowed fields from payload
    updatable = (
        "full_name",
        "roll_no",
        "dept",
        "section",
        "series",
        "mobile_no",
        "email",
        "profile_image",
    )

    for field in updatable:
        val = getattr(payload, field, None)
        if val is not None:
            setattr(db_student, field, val)

    db.commit()
    db.refresh(db_student)

    # return a simple dict representation
    return {
        "message": "Profile updated",
        "profile": {
            "neura_id": db_student.neura_id,
            "full_name": db_student.full_name,
            "roll_no": db_student.roll_no,
            "dept": db_student.dept,
            "section": db_student.section,
            "series": db_student.series,
            "mobile_no": db_student.mobile_no,
            "email": db_student.email,
            "profile_image": db_student.profile_image,
        },
    }
