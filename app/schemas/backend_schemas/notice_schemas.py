from pydantic import BaseModel, Field, field_validator
from typing import Optional,Literal
from datetime import datetime


class TeacherNoticeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    notice_message: str = Field(..., min_length=1)

    dept: str
    sec: str
    series: str

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
        return value.upper()

    @field_validator("series")
    def validate_series(cls, value):
        if value is None:
            return value

        try:
            value_int = int(value)
        except ValueError:
            raise ValueError("Series must be a number between 19 and 25")

        if value_int < 19 or value_int > 25:
            raise ValueError("Series must be between 19 and 25")

        return value  # keep original string (DO NOT change business logic)

    @field_validator("sec")
    def validate_section(cls, value):
        if value not in (None, "A", "B", "C"):
            raise ValueError("Section must be A, B, C or None")
        return value

        return value

class CRNoticeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    notice_message: str = Field(..., min_length=1)


class NoticeResponse(BaseModel):
    id: str
    title: str
    notice_message: str

    created_by_role: Literal["teacher", "cr"]
    created_by_teacher_id: Optional[str] = None
    created_by_cr_id: Optional[str] = None

    dept: str
    sec: str
    series: str

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeacherNoticeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    notice_message: Optional[str] = Field(None, min_length=1)

    # teacher can change targeting too
    dept: Optional[str] = None
    sec: Optional[str] = None
    series: Optional[str] = None


class CRNoticeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    notice_message: Optional[str] = Field(None, min_length=1)