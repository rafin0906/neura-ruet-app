from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.student_models import Student

bearer_scheme = HTTPBearer(auto_error=False)

def get_student_from_setup_token(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    token = creds.credentials

    student = (
        db.query(Student)
        .filter(Student.setup_token == token)
        .first()
    )

    if not student:
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")

    return student
