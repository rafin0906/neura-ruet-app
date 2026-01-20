from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.models.student_models import Student
from app.models.teacher_models import Teacher
from app.models.cr_models import CR

from app.services.dependencies import (
    get_current_student,
    get_current_teacher,
    get_current_cr,
)

from app.schemas.password_update_schemas import PasswordUpdateIn
from app.utils.hashing import verify_password, get_password_hash


router = APIRouter(prefix="/update-password", tags=["Update Password"])


def _change_password(user_obj, payload: PasswordUpdateIn, db: Session):
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")

    if not getattr(user_obj, "password", None):
        raise HTTPException(status_code=400, detail="Password not set")

    if not verify_password(payload.current_password, user_obj.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password incorrect",
        )

    user_obj.password = get_password_hash(payload.new_password)

    db.commit()


@router.put("/students", status_code=status.HTTP_200_OK)
def update_student_password(
    payload: PasswordUpdateIn,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    _change_password(student, payload, db)
    return {"message": "Password updated successfully"}


@router.put("/teachers", status_code=status.HTTP_200_OK)
def update_teacher_password(
    payload: PasswordUpdateIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    _change_password(teacher, payload, db)
    return {"message": "Password updated successfully"}


@router.put("/crs", status_code=status.HTTP_200_OK)
def update_cr_password(
    payload: PasswordUpdateIn,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    _change_password(cr, payload, db)
    return {"message": "Password updated successfully"}

