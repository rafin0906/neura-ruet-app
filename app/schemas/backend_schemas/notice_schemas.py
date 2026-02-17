from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime


def _normalize_section(value: Optional[str]) -> Optional[str]:
    # Accept None/null and also common "None" string variants.
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return None
        if cleaned.lower() in {"none", "null"}:
            return None
        cleaned_upper = cleaned.upper()
        if cleaned_upper in {"A", "B", "C"}:
            return cleaned_upper
    raise ValueError("Section must be A, B, C or None")


class TeacherNoticeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    notice_message: str = Field(..., min_length=1)

    dept: str
    sec: Optional[str] = None
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
        return _normalize_section(value)

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
    sec: Optional[str] = None
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

    @field_validator("sec")
    def validate_section(cls, value):
        # allow explicit null + allow sending "None"
        return _normalize_section(value)


class CRNoticeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    notice_message: Optional[str] = Field(None, min_length=1)