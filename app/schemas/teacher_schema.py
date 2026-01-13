from pydantic import BaseModel, EmailStr, constr, field_validator
from typing import Optional


class TeacherSchema(BaseModel):
    full_name: str
    designation: str
    dept: str
    joining_year: int
    mobile_no: Optional[str]
    email: EmailStr
    neura_teacher_id: str
    profile_image: Optional[str]

    @field_validator("designation")
    def validate_designation(cls, value):
        allowed_designations = [
            "professor",
            "associate professor",
            "assistant professor",
            "lecturer",
        ]
        if value.lower() not in allowed_designations:
            raise ValueError(f"Designation must be one of {allowed_designations}")
        return value

    @field_validator("dept")
    def validate_dept(cls, value):
        allowed_depts = [
            "CSE",
            "EEE",
            "ME",
            "CE",
            "IPE",
            "ETE",
            "URP",
            "ARCH",
            "BME",
            "MTE",
            "GCE",
            "WRE",
        ]
        if value.upper() not in allowed_depts:
            raise ValueError(f"Department must be one of {allowed_depts}")
        return value



class TeacherLoginSchema(BaseModel):
    neura_teacher_id: str
    password: constr(min_length=3)