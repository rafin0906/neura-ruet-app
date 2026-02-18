from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import jwt
import os
import random
import secrets
import resend
from email.message import EmailMessage
from datetime import datetime, timedelta
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.db.database import get_db
from app.models.teacher_models import Teacher
from app.schemas.backend_schemas.teacher_schema import (
    TeacherLoginSchema,
    TeacherSchema,
    TeacherProfileSetupMeResponse,
)
from app.schemas.backend_schemas.utils_schema import (
    ForgetPasswordSchema,
    ResetPasswordSchema,
)

from app.utils.hashing import (
    get_password_hash,
    hash_refresh_token,
    verify_refresh_token,
    verify_password,
)
from app.utils.logger import logger
from app.services.profile_set_up_dependencies import get_teacher_for_profile_setup
from app.services.dependencies import (
    create_access_token,
    get_current_teacher,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    ALGORITHM,
)

REFRESH_TOKEN_EXPIRE_DAYS = 30
otp_store = {}
refresh_bearer = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/teachers", tags=["Teachers"])


def _mask_otp(otp: str) -> str:
    if not otp or len(otp) < 2:
        return "**"
    return "*" * (len(otp) - 1) + otp[-1]


def sanitize_otp_store() -> dict:
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
    now = datetime.utcnow()
    expired = [
        email
        for email, e in otp_store.items()
        if e.get("expires") and e["expires"] < now
    ]
    for email in expired:
        logger.debug("Removing expired OTP for %s", email)
        del otp_store[email]


@router.post("/login")
def teacher_login(payload: TeacherLoginSchema, db: Session = Depends(get_db)):
    teacher = (
        db.query(Teacher)
        .filter(Teacher.neura_teacher_id == payload.neura_teacher_id)
        .first()
    )
    if not teacher:
        raise HTTPException(status_code=400, detail="Neura Teacher ID invalid")

    if not verify_password(payload.password, teacher.password):
        raise HTTPException(status_code=400, detail="Password invalid")

    setup_token = secrets.token_urlsafe(32)
    teacher.setup_token = setup_token
    db.commit()

    return {"login_ok": True, "setup_token": setup_token}


@router.post("/forget-password")
def teacher_forget_password(
    payload: ForgetPasswordSchema, db: Session = Depends(get_db)
):
    teacher = db.query(Teacher).filter(Teacher.email == payload.email).first()
    if not teacher:
        raise HTTPException(400, "Email not found")

    cleanup_expired_otps()
    otp = f"{random.randint(1000, 9999)}"
    expires = datetime.utcnow() + timedelta(minutes=10)
    otp_store[payload.email] = {"otp": otp, "expires": expires}

    logger.info(
        "Generated OTP for %s (masked=%s), expires=%s",
        payload.email,
        _mask_otp(otp),
        expires.isoformat(),
    )

    subject = "Your password reset OTP"
    body = f"Your password reset OTP is: {otp}. It will expire in 10 minutes."

    # Use Resend (HTTPS) when configured; fall back to logging otherwise.
    resend_api_key = os.getenv("RESEND_API_KEY")
    if resend_api_key:
        resend.api_key = resend_api_key
        try:
            resend.Emails.send(
                {
                    "from": "onboarding@resend.dev",
                    "to": payload.email,
                    "subject": subject,
                    "text": body,
                }
            )
            logger.info("Sent OTP email to %s via Resend", payload.email)
        except Exception:
            logger.exception("Failed to send OTP email via Resend")
            raise HTTPException(status_code=500, detail="Failed to send OTP email")
    else:
        logger.info(
            "Resend not configured; OTP generated for %s (masked=%s)",
            payload.email,
            _mask_otp(otp),
        )
        logger.debug("Full OTP for %s: %s", payload.email, otp)

    return {"message": "OTP sent to your email"}


@router.post("/reset-password")
def teacher_reset_password(payload: ResetPasswordSchema, db: Session = Depends(get_db)):
    teacher = db.query(Teacher).filter(Teacher.email == payload.email).first()
    if not teacher:
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

    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Confirm Password does not match")

    teacher.password = get_password_hash(payload.new_password)
    db.commit()
    del otp_store[payload.email]

    return {"message": "Password reset successful"}


@router.get("/profile-setup/me", response_model=TeacherProfileSetupMeResponse)
def teacher_profile_setup_me(teacher: Teacher = Depends(get_teacher_for_profile_setup)):
    return teacher


@router.post("/profile-setup")
def teacher_profile_setup(
    payload: TeacherSchema,
    teacher: Teacher = Depends(get_teacher_for_profile_setup),
    db: Session = Depends(get_db),
):
    # ✅ unique checks (only if user is updating it)
    if payload.email and payload.email != teacher.email:
        exists = (
            db.query(Teacher)
            .filter(Teacher.email == payload.email, Teacher.id != teacher.id)
            .first()
        )
        if exists:
            raise HTTPException(
                status_code=409,
                detail="Email already used by another teacher",
            )

    if payload.mobile_no and payload.mobile_no != teacher.mobile_no:
        exists = (
            db.query(Teacher)
            .filter(Teacher.mobile_no == payload.mobile_no, Teacher.id != teacher.id)
            .first()
        )
        if exists:
            raise HTTPException(
                status_code=409, detail="Mobile number already used by another teacher"
            )

    updatable = (
        "full_name",
        "designation",
        "dept",
        "joining_year",
        "mobile_no",
        "email",
        "profile_image",
    )

    for field in updatable:
        val = getattr(payload, field, None)
        if val is not None:
            setattr(teacher, field, val)

    # clear setup token only if still present
    if teacher.setup_token:
        teacher.setup_token = None

    # tokens...
    access_token = create_access_token(
        data={
            "neura_teacher_id": teacher.neura_teacher_id,
            "token_version": teacher.token_version,
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = secrets.token_urlsafe(48)
    refresh_token_id = secrets.token_urlsafe(16)

    teacher.refresh_token_id = refresh_token_id
    teacher.refresh_token_hash = hash_refresh_token(refresh_token)
    teacher.refresh_token_expires_at = datetime.utcnow() + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    # ✅ commit safely (handles race conditions)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unique constraint failed")

    db.refresh(teacher)

    return {
        "message": "Profile updated",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "refresh_token_id": refresh_token_id,
        "token_type": "bearer",
        "profile": {
            "neura_teacher_id": teacher.neura_teacher_id,
            "full_name": teacher.full_name,
            "designation": teacher.designation,
            "dept": teacher.dept,
            "joining_year": teacher.joining_year,
            "mobile_no": teacher.mobile_no,
            "email": teacher.email,
            "profile_image": teacher.profile_image,
        },
    }


@router.post("/refresh")
def teacher_refresh_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(refresh_bearer),
    x_refresh_id: str = Header(..., alias="X-Refresh-Id"),
    x_access_token: str = Header(..., alias="X-Access-Token"),
    db: Session = Depends(get_db),
):
    # 0) refresh token from Authorization: Bearer <refresh_token>
    if not credentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Authorization header missing"
        )

    refresh_token = credentials.credentials

    # 1) access token must be expired
    try:
        jwt.decode(x_access_token, SECRET_KEY, algorithms=[ALGORITHM])
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Access token not expired yet")
    except ExpiredSignatureError:
        pass
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token")

    # 2) decode expired token (ignore exp) to read claims
    try:
        expired_payload = jwt.decode(
            x_access_token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token")

    # 3) lookup teacher by refresh_token_id
    teacher = db.query(Teacher).filter(Teacher.refresh_token_id == x_refresh_id).first()
    if not teacher or not teacher.refresh_token_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    # 4) verify refresh token hash
    if not verify_refresh_token(refresh_token, teacher.refresh_token_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    # 5) refresh token expiry check
    if (
        not teacher.refresh_token_expires_at
        or datetime.utcnow() > teacher.refresh_token_expires_at
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired")

    # 6) bind refresh to the expired access token + token_version
    if expired_payload.get("neura_teacher_id") != teacher.neura_teacher_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token mismatch")

    if expired_payload.get("token_version") != teacher.token_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revoked")

    # ✅ 7) issue new access token
    new_access_token = create_access_token(
        data={
            "neura_teacher_id": teacher.neura_teacher_id,
            "token_version": teacher.token_version,
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    # ✅ 8) ROTATE refresh token (new one replaces old)
    new_refresh_token = secrets.token_urlsafe(48)
    new_refresh_token_id = secrets.token_urlsafe(16)

    teacher.refresh_token_id = new_refresh_token_id
    teacher.refresh_token_hash = hash_refresh_token(new_refresh_token)
    teacher.refresh_token_expires_at = datetime.utcnow() + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    db.commit()
    db.refresh(teacher)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "refresh_token_id": new_refresh_token_id,
        "token_type": "bearer",
    }


@router.post("/logout")
def teacher_logout(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    teacher.token_version += 1
    teacher.refresh_token_id = None
    teacher.refresh_token_hash = None
    teacher.refresh_token_expires_at = None
    db.commit()
    return {"message": "Logged out successfully"}
