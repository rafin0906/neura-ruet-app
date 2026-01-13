from fastapi import FastAPI, HTTPException, status, Response, Depends, APIRouter
from sqlalchemy.orm import Session
from app.core.database import get_db
from typing import List
from app.models.cr_models import CR
from app.schemas.teacher_schema import TeacherLoginSchema

router = APIRouter(
    prefix="/teaches",
    tags= ['Teachers']
)


@router.post("/login")
def login(
    payload: TeacherLoginSchema,
    db: Session = Depends(get_db)
):
    # check duplicate
    db_teacher = db.query(Teacher).filter(
        Teacher.neura_teacher_id == payload.neura_teacher_id
    ).first()
    if not db_teacher:
        raise HTTPException(400, "Neura Teacher ID invalid")

    if db_teacher.password != payload.password:
        raise HTTPException(400, "Password invalid")
    
    return {"message": "Login successful"}
