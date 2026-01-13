from pydantic import BaseModel, EmailStr, constr, field_validator
from typing import Optional
from app.schemas.student_schemas import StudentSchema


class CRSchema(StudentSchema):
    or_no: str
    neura_or_id: str

    # Additional validations can be added here if needed



class CRLoginSchema(BaseModel):
    neura_or_id: str
    password: constr(min_length=3)