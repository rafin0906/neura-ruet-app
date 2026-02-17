from pydantic import BaseModel, EmailStr, constr, field_validator
from typing import Optional
from typing_extensions import Literal

from app.schemas.backend_schemas.student_schemas import StudentBaseSchema


class CRBaseSchema(StudentBaseSchema):
    cr_no: Optional[str] = None

    @field_validator("cr_no")
    def validate_cr_no(cls, value):
        if value is None:
            return value

        allowed = ["cr-1", "cr-2", "cr-3"]

        cr = value.strip().lower()  # normalize
        if cr not in allowed:
            raise ValueError(f"cr_no must be one of {allowed}")

        return cr  # always saved as "cr-1"/"cr-2"/"cr-3"


class CRSchema(CRBaseSchema):

    full_name: str
    dept: str
    section: Optional[str] = None
    series: int

    mobile_no: str
    email: EmailStr

    cr_no: str  # required


class CRLoginSchema(BaseModel):
    neura_cr_id: str
    password: constr(min_length=3)


class CRProfileSetupMeResponse(BaseModel):
    neura_cr_id: str

    full_name: Optional[str] = None
    roll_no: Optional[str] = None
    dept: Optional[str] = None
    section: Optional[Literal["A", "B", "C"]] = None
    series: Optional[int] = None

    mobile_no: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    cr_no: Optional[str] = None

    class Config:
        from_attributes = True
