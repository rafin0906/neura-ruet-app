from pydantic import BaseModel, EmailStr, constr, field_validator
from typing import Optional


class TeacherBaseSchema(BaseModel):
    full_name: Optional[str] = None
    designation: Optional[str] = None
    dept: Optional[str] = None
    joining_year: Optional[int] = None
    mobile_no: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None

    @field_validator("designation")
    def validate_designation(cls, value):
        if value is None:
            return value
        allowed_designations = [
            "professor",
            "associate professor",
            "assistant professor",
            "lecturer",
        ]
        if value.lower() not in allowed_designations:
            raise ValueError(f"Designation must be one of {allowed_designations}")
        return value.lower()

    @field_validator("dept")
    def validate_dept(cls, value):
        if value is None:
            return value
        allowed_depts = [
            "EEE","CSE","ETE","ECE","CE","URP",
            "ARCH","BECM","ME","IPE","CME","MTE","MSE","CHE"
        ]
        if value.upper() not in allowed_depts:
            raise ValueError(f"Department must be one of {allowed_depts}")
        return value.upper()

    @field_validator("joining_year")
    def validate_joining_year(cls, value):
        if value is None:
            return value
        # optional: simple sanity check (you can remove if you want)
        if value < 1990 or value > 2100:
            raise ValueError("Joining year looks invalid")
        return value


class TeacherSchema(TeacherBaseSchema):
    # matches StudentSchema pattern: required fields + id required
    full_name: str
    designation: str
    dept: str
    joining_year: int
    email: EmailStr
    mobile_no: str


class TeacherLoginSchema(BaseModel):
    neura_teacher_id: str
    password: constr(min_length=3)


class TeacherProfileSetupMeResponse(BaseModel):
    neura_teacher_id: str
    full_name: Optional[str] = None
    designation: Optional[str] = None
    dept: Optional[str] = None
    joining_year: Optional[int] = None
    mobile_no: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None

    class Config:
        from_attributes = True
