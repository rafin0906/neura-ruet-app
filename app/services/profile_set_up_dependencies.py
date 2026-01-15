from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.student_models import Student
from app.models.teacher_models import Teacher
from app.models.cr_models import CR
from app.services.dependencies import http_bearer, verify_access_token, _get_bearer_token


def get_student_for_profile_setup(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> Student:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _get_bearer_token(credentials, credentials_exception)

    # ✅ If looks like JWT (a.b.c) => use access token flow
    if token.count(".") == 2:
        payload = verify_access_token(token, credentials_exception)

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

    # ✅ Otherwise treat as setup token
    student = db.query(Student).filter(Student.setup_token == token).first()
    if not student:
        raise HTTPException(status_code=401, detail="Invalid setup token")

    return student

def get_teacher_for_profile_setup(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> Teacher:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _get_bearer_token(credentials, credentials_exception)

    # ✅ JWT-like => access token flow
    if token.count(".") == 2:
        payload = verify_access_token(token, credentials_exception)

        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Access token required")

        neura_teacher_id = payload.get("neura_teacher_id")
        if not neura_teacher_id:
            raise credentials_exception

        teacher = (
            db.query(Teacher)
            .filter(Teacher.neura_teacher_id == neura_teacher_id)
            .first()
        )
        if not teacher:
            raise credentials_exception

        token_ver = payload.get("token_version")
        if token_ver is None or token_ver != teacher.token_version:
            raise HTTPException(status_code=401, detail="Token has been revoked")

        return teacher

    # ✅ otherwise => setup token flow
    teacher = db.query(Teacher).filter(Teacher.setup_token == token).first()
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid setup token")

    return teacher


def get_cr_for_profile_setup(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> CR:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _get_bearer_token(credentials, credentials_exception)

    # ✅ JWT-like => access token flow
    if token.count(".") == 2:
        payload = verify_access_token(token, credentials_exception)

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

    # ✅ otherwise => setup token flow
    cr = db.query(CR).filter(CR.setup_token == token).first()
    if not cr:
        raise HTTPException(status_code=401, detail="Invalid setup token")

    return cr
