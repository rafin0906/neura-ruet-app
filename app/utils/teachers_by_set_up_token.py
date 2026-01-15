from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.teacher_models import Teacher

bearer_scheme = HTTPBearer(auto_error=False)


def get_teacher_from_setup_token(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    token = creds.credentials

    teacher = (
        db.query(Teacher)
        .filter(Teacher.setup_token == token)
        .first()
    )

    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")

    return teacher
