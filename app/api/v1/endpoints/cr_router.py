from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import jwt
import os
import random
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.db.database import get_db
from app.models.cr_models import CR
from app.schemas.cr_schemas import CRLoginSchema, CRSchema, CRProfileSetupMeResponse
from app.schemas.utils_schema import ForgetPasswordSchema, ResetPasswordSchema

from app.utils.hashing import (
    get_password_hash,
    hash_refresh_token,
    verify_refresh_token,
    verify_password,
)
from app.utils.logger import logger
from app.services.profile_set_up_dependencies import get_cr_for_profile_setup
from app.services.dependencies import (
    create_access_token,
    get_current_cr,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    ALGORITHM,
)


refresh_bearer = HTTPBearer(auto_error=False)
REFRESH_TOKEN_EXPIRE_DAYS = 30
otp_store = {}

router = APIRouter(prefix="/crs", tags=["CRs"])


def _mask_otp(otp: str) -> str:
    if not otp or len(otp) < 2:
        return "**"
    return "*" * (len(otp) - 1) + otp[-1]


def sanitize_otp_store() -> dict:
    sanitized = {}
    for email, entry in otp_store.items():
        sanitized[email] = {
            "otp": _mask_otp(entry.get("otp")),
            "expires": entry.get("expires").isoformat() if entry.get("expires") else None,
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
def cr_login(payload: CRLoginSchema, db: Session = Depends(get_db)):
    cr = db.query(CR).filter(CR.neura_cr_id == payload.neura_cr_id).first()
    if not cr:
        raise HTTPException(status_code=400, detail="Neura CR ID invalid")

    if not verify_password(payload.password, cr.password):
        raise HTTPException(status_code=400, detail="Password invalid")

    setup_token = secrets.token_urlsafe(32)
    cr.setup_token = setup_token
    db.commit()

    return {"login_ok": True, "setup_token": setup_token}


@router.post("/forget-password")
def cr_forget_password(payload: ForgetPasswordSchema, db: Session = Depends(get_db)):
    cr = db.query(CR).filter(CR.email == payload.email).first()
    if not cr:
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
        except Exception:
            logger.exception("Failed to send OTP email")
            raise HTTPException(status_code=500, detail="Failed to send OTP email")
    else:
        logger.info(
            "SMTP not configured; OTP generated for %s (masked=%s)",
            payload.email,
            _mask_otp(otp),
        )
        logger.debug("Full OTP for %s: %s", payload.email, otp)

    return {"message": "OTP sent to your email"}


@router.post("/reset-password")
def cr_reset_password(payload: ResetPasswordSchema, db: Session = Depends(get_db)):
    cr = db.query(CR).filter(CR.email == payload.email).first()
    if not cr:
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

    cr.password = get_password_hash(payload.new_password)
    db.commit()
    del otp_store[payload.email]

    return {"message": "Password reset successful"}




@router.get("/profile-setup/me", response_model=CRProfileSetupMeResponse)
def cr_profile_setup_me(cr: CR = Depends(get_cr_for_profile_setup)):
    return cr


@router.post("/profile-setup")
def cr_profile_setup(
    payload: CRSchema,
    cr: CR = Depends(get_cr_for_profile_setup),
    db: Session = Depends(get_db),
):
    # ✅ UNIQUE checks (only if user changes them)

    if payload.roll_no and payload.roll_no != cr.roll_no:
        exists = (
            db.query(CR)
            .filter(CR.roll_no == payload.roll_no, CR.id != cr.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Roll no already used by another CR")

    if payload.email and payload.email != cr.email:
        exists = (
            db.query(CR)
            .filter(CR.email == payload.email, CR.id != cr.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Email already used by another CR")

    if payload.mobile_no and payload.mobile_no != cr.mobile_no:
        exists = (
            db.query(CR)
            .filter(CR.mobile_no == payload.mobile_no, CR.id != cr.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Mobile number already used")


    # ✅ update allowed fields only
    updatable = (
        "full_name",
        "roll_no",
        "dept",
        "section",
        "series",
        "mobile_no",
        "email",
        "profile_image",
        "cr_no",
    )

    for field in updatable:
        val = getattr(payload, field, None)
        if val is not None:
            setattr(cr, field, val)

    # 🔒 invalidate setup token only if still present
    if cr.setup_token:
        cr.setup_token = None

    # ✅ issue tokens
    access_token = create_access_token(
        data={
            "neura_cr_id": cr.neura_cr_id,
            "token_version": cr.token_version,
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = secrets.token_urlsafe(48)
    refresh_token_id = secrets.token_urlsafe(16)

    cr.refresh_token_id = refresh_token_id
    cr.refresh_token_hash = hash_refresh_token(refresh_token)
    cr.refresh_token_expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # ✅ commit safely (race-condition proof)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unique constraint failed")

    db.refresh(cr)

    return {
        "message": "Profile updated",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "refresh_token_id": refresh_token_id,
        "token_type": "bearer",
        "profile": {
            "neura_cr_id": cr.neura_cr_id,
            "full_name": cr.full_name,
            "roll_no": cr.roll_no,
            "dept": cr.dept,
            "section": cr.section,
            "series": cr.series,
            "mobile_no": cr.mobile_no,
            "email": cr.email,
            "profile_image": cr.profile_image,
            "cr_no": cr.cr_no,
        },
    }



@router.post("/refresh")
def cr_refresh_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(refresh_bearer),
    x_refresh_id: str = Header(..., alias="X-Refresh-Id"),
    x_access_token: str = Header(..., alias="X-Access-Token"),
    db: Session = Depends(get_db),
):
    # 0) refresh token from Authorization: Bearer <refresh_token>
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authorization header missing")

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

    # 3) lookup CR by refresh_token_id
    cr = (
        db.query(CR)
        .filter(CR.refresh_token_id == x_refresh_id)
        .first()
    )
    if not cr or not cr.refresh_token_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    if not verify_refresh_token(refresh_token, cr.refresh_token_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    if not cr.refresh_token_expires_at or datetime.utcnow() > cr.refresh_token_expires_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired")

    # 4) bind refresh to the expired access token
    if expired_payload.get("neura_cr_id") != cr.neura_cr_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token mismatch")

    if expired_payload.get("token_version") != cr.token_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revoked")

    # 5) issue new access token
    new_access_token = create_access_token(
        data={
            "neura_cr_id": cr.neura_cr_id,
            "token_version": cr.token_version,
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout")
def cr_logout(
    cr: CR = Depends(get_current_cr),
    db: Session = Depends(get_db),
):
    cr.token_version += 1
    cr.refresh_token_id = None
    cr.refresh_token_hash = None
    cr.refresh_token_expires_at = None
    db.commit()
    return {"message": "Logged out successfully"}
