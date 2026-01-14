from pydantic import BaseModel, EmailStr, constr, field_validator
from typing import Optional
from app.schemas.student_schemas import StudentSchema


class CRSchema(StudentSchema):
    neura_id: None = None      #  remove student neura_id
    neura_cr_id: str           #  CR-specific ID
    cr_no: str


class CRLoginSchema(BaseModel):
    neura_cr_id: str
    password: constr(min_length=3)