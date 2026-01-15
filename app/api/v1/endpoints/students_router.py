from fastapi import FastAPI, HTTPException, status, Response, Depends, APIRouter, Header
from sqlalchemy.orm import Session
from app.core.database import get_db
from typing import List

import jwt
import secrets
import os
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta , timezone
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError


from app.models.student_models import Student
from app.schemas.student_schemas import StudentLoginSchema, StudentSchema, ProfileSetupMeResponse
from app.schemas.utils_schema import ForgetPasswordSchema
from app.schemas.utils_schema import ResetPasswordSchema
from app.utils.hashing import get_password_hash, hash_refresh_token, verify_refresh_token
from app.utils.hashing import verify_password
from app.utils.logger import logger
from app.utils.students_by_set_up_token import get_student_from_setup_token
from app.services.dependencies import create_access_token, get_current_student
from app.services.dependencies import ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM



REFRESH_TOKEN_EXPIRE_DAYS = 30
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
    db_student = db.query(Student).filter(Student.neura_id == payload.neura_id).first()

    if not db_student:
        raise HTTPException(status_code=400, detail="Neura ID invalid")

    if not verify_password(payload.password, db_student.password):
        raise HTTPException(status_code=400, detail="Password invalid")

    # 🔐 generate temporary setup token
    setup_token = secrets.token_urlsafe(32)
    db_student.setup_token = setup_token
    db.commit()

    return {"login_ok": True, "setup_token": setup_token}


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



@router.get("/profile-setup/me", response_model=ProfileSetupMeResponse)
def get_profile_setup_data(student: Student = Depends(get_student_from_setup_token)):
    return student




@router.post("/profile-setup")
def profile_setup(
    payload: StudentSchema,
    student: Student = Depends(get_student_from_setup_token),
    db: Session = Depends(get_db),
):
    updatable = (
        "full_name", "roll_no", "dept", "section",
        "series", "mobile_no", "email", "profile_image",
    )

    for field in updatable:
        val = getattr(payload, field, None)
        if val is not None:
            setattr(student, field, val)

    # 🔒 invalidate setup token after use
    student.setup_token = None

    # ✅ ACCESS TOKEN (JWT, short)
    access_token = create_access_token(
        data={
            "neura_id": student.neura_id,
            "token_version": student.token_version,   # helpful for global logout later
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    # ✅ REFRESH TOKEN (random secret, long)
    refresh_token = secrets.token_urlsafe(48)     # secret (store in app securely)
    refresh_token_id = secrets.token_urlsafe(16)  # non-secret lookup key

    student.refresh_token_id = refresh_token_id
    student.refresh_token_hash = hash_refresh_token(refresh_token)
    student.refresh_token_expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db.commit()
    db.refresh(student)

    return {
        "message": "Profile updated",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "refresh_token_id": refresh_token_id,  # optional to return; useful for refresh endpoint
        "token_type": "bearer",
        "profile": {
            "neura_id": student.neura_id,
            "full_name": student.full_name,
            "roll_no": student.roll_no,
            "dept": student.dept,
            "section": student.section,
            "series": student.series,
            "mobile_no": student.mobile_no,
            "email": student.email,
            "profile_image": student.profile_image,
        },
    }

@router.post("/refresh")
def refresh_access_token(
    authorization: str = Header(...),
    x_refresh_id: str = Header(..., alias="X-Refresh-Id"),
    x_access_token: str = Header(..., alias="X-Access-Token"),
    db: Session = Depends(get_db),
):
    # 1) Access token must be expired BUT still decodable (ignore exp to read claims)
    try:
        # This will raise ExpiredSignatureError if expired (good)
        jwt.decode(x_access_token, SECRET_KEY, algorithms=[ALGORITHM])
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Access token not expired yet")
    except ExpiredSignatureError:
        pass
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token")

    # ✅ decode again WITHOUT verifying exp so we can read claims safely
    try:
        expired_payload = jwt.decode(
            x_access_token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token")

    # 2) Refresh token checks
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")
    refresh_token = authorization.replace("Bearer ", "").strip()

    student = db.query(Student).filter(Student.refresh_token_id == x_refresh_id).first()
    if not student or not student.refresh_token_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    if not verify_refresh_token(refresh_token, student.refresh_token_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    if not student.refresh_token_expires_at or datetime.utcnow() > student.refresh_token_expires_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired")

    # ✅ token_version enforcement during refresh
    if expired_payload.get("neura_id") != student.neura_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token mismatch")

    if expired_payload.get("token_version") != student.token_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revoked")

    new_access_token = create_access_token(
        data={
            "neura_id": student.neura_id,
            "token_version": student.token_version,
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {"access_token": new_access_token, "token_type": "bearer"}



@router.post("/logout")
def logout(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    # ✅ invalidate ALL access tokens immediately
    student.token_version += 1

    # ✅ also kill refresh token (important)
    student.refresh_token_id = None
    student.refresh_token_hash = None
    student.refresh_token_expires_at = None

    db.commit()

    return {"message": "Logged out successfully"}