import os
import jwt
from datetime import datetime, timedelta, timezone
from jwt.exceptions import InvalidTokenError

from fastapi import Depends, status, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.student_models import Student
from app.models.teacher_models import Teacher
from app.models.cr_models import CR


# ✅ HTTPBearer for extracting Bearer token from Authorization header
http_bearer = HTTPBearer(auto_error=False)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing in .env")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str, credentials_exception: HTTPException) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        raise credentials_exception


def _get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None,
    credentials_exception: HTTPException
) -> str:
    if not credentials or not credentials.scheme or credentials.scheme.lower() != "bearer":
        raise credentials_exception
    token = credentials.credentials
    if not token:
        raise credentials_exception
    return token


def get_current_student(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db)
) -> Student:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _get_bearer_token(credentials, credentials_exception)
    payload = verify_access_token(token, credentials_exception)

    # ✅ token type check (optional but recommended)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    neura_id = payload.get("neura_id")
    if not neura_id:
        raise credentials_exception

    student = db.query(Student).filter(Student.neura_id == neura_id).first()
    if not student:
        raise credentials_exception
    
    token_ver = payload.get("token_version")
    if token_ver is None or token_ver != student.token_version:
        raise HTTPException(status_code=401, detail="Token has been revoked")


    return student


def get_current_teacher(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db)
) -> Teacher:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _get_bearer_token(credentials, credentials_exception)
    payload = verify_access_token(token, credentials_exception)

    # ✅ token type check (optional but recommended)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    neura_teacher_id = payload.get("neura_teacher_id")
    if not neura_teacher_id:
        raise credentials_exception

    teacher = db.query(Teacher).filter(Teacher.neura_teacher_id == neura_teacher_id).first()
    if not teacher:
        raise credentials_exception

    token_ver = payload.get("token_version")
    if token_ver is None or token_ver != teacher.token_version:
        raise HTTPException(status_code=401, detail="Token has been revoked")


    return teacher


def get_current_cr(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db)
) -> CR:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _get_bearer_token(credentials, credentials_exception)
    payload = verify_access_token(token, credentials_exception)

    # ✅ token type check (optional but recommended)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    neura_cr_id = payload.get("neura_cr_id")
    if not neura_cr_id:
        raise credentials_exception

    cr = db.query(CR).filter(CR.neura_cr_id == neura_cr_id).first()
    if not cr:
        raise credentials_exception
    
    token_ver = payload.get("token_version")
    if token_ver is None or token_ver != cr.token_version:
        raise HTTPException(status_code=401, detail="Token has been revoked")


    return cr


