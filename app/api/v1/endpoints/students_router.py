from fastapi import FastAPI, HTTPException, status, Response, Depends, APIRouter
from sqlalchemy.orm import Session
from app.core.database import get_db
from typing import List
from app.models.student_models import Student
from app.schemas.student_schemas import StudentLoginSchema

router = APIRouter(
    prefix="/students",
    tags= ['Students']
)


@router.post("/login")
def login(
    payload: StudentLoginSchema,
    db: Session = Depends(get_db)
):
    # check duplicate
    db_student = db.query(Student).filter(
        Student.neura_id == payload.neura_id
    ).first()
    if not db_student:
        raise HTTPException(400, "Neura ID invalid")

    if db_student.password != payload.password:
        raise HTTPException(400, "Password invalid")
    
    return {"message": "Login successful"}


# @router.post("")