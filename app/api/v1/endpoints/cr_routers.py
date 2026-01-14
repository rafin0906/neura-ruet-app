from fastapi import FastAPI, HTTPException, status, Response, Depends, APIRouter
from sqlalchemy.orm import Session
from app.core.database import get_db
from typing import List
from app.models.cr_models import CR
from app.schemas.cr_schemas import CRLoginSchema


router = APIRouter(
    prefix="/cr",
    tags= ['CR']
)


@router.post("/login")
def login(
    payload: CRLoginSchema,
    db: Session = Depends(get_db)
):
    # check duplicate
    db_teacher = db.query(CR).filter(
        CR.neura_cr_id == payload.neura_cr_id
    ).first()
    if not db_teacher:
        raise HTTPException(400, "Neura CR ID invalid")

    if db_teacher.password != payload.password:
        raise HTTPException(400, "Password invalid")
    
    return {"message": "Login successful"}
