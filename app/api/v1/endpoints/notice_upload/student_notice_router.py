from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.backend_schemas.notice_schemas import NoticeResponse
from app.services.dependencies import get_current_student
from app.services.notice_service import get_student_notices
from app.models.student_models import Student

router = APIRouter(prefix="/student/notices", tags=["Notices (Student)"])


@router.get("", response_model=list[NoticeResponse])
def get_notices_for_student(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return get_student_notices(db=db, student=student, skip=skip, limit=limit)
