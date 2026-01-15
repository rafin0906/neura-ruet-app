from pydantic import BaseModel, EmailStr, constr, field_validator
from typing import Optional
from typing_extensions import Literal

class StudentBaseSchema(BaseModel):
    full_name: Optional[str] = None
    roll_no: Optional[str] = None
    dept: Optional[str] = None
    section: Optional[str] = None
    series: Optional[int] = None
    mobile_no: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None

    @field_validator("dept")
    def validate_dept(cls, value):
        if value is None:
            return value
        allowed_depts = [
            "CSE","EEE","ME","CE","IPE","ETE",
            "URP","ARCH","BME","MTE","GCE","WRE"
        ]
        if value.upper() not in allowed_depts:
            raise ValueError(f"Department must be one of {allowed_depts}")
        return value

    @field_validator("series")
    def validate_series(cls, value):
        if value is None:
            return value
        if value < 19 or value > 25:
            raise ValueError("Series must be between 19 and 25")
        return value

    @field_validator("section")
    def validate_section(cls, value):
        if value not in (None, "A", "B", "C"):
            raise ValueError("Section must be A, B, C or None")
        return value


class StudentLoginSchema(BaseModel):
    neura_id: str
    password: constr(min_length=3)

class StudentSchema(StudentBaseSchema):
    neura_id: str
    full_name: str
    roll_no: str
    dept: str
    series: int
    email: EmailStr
    mobile_no: str
    section: str


class ProfileSetupMeResponse(BaseModel):
    neura_id: str

    full_name: Optional[str] = None
    roll_no: Optional[str] = None

    dept: Optional[str] = None
    section: Optional[Literal["A", "B", "C"]] = None
    series: Optional[int] = None

    mobile_no: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None

    class Config:
        from_attributes = True  # pydantic v2: lets you validate from ORM objects