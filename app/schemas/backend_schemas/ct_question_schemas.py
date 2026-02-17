from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional
from datetime import datetime


class CRCTQuestionCreate(BaseModel):
    drive_url: HttpUrl
    course_code: str = Field(..., min_length=1, max_length=50)
    course_name: str = Field(..., min_length=1, max_length=200)
    ct_no: int = Field(..., ge=1, le=20)

    @field_validator("course_code")
    @classmethod
    def uppercase_course_code(cls, v: str) -> str:
        return v.upper()


class CTQuestionResponse(BaseModel):
    id: str
    drive_url: str

    course_code: str
    course_name: str
    ct_no: int

    uploaded_by_cr_id: str

    dept: str
    sec: Optional[str] = None
    series: str

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CRCTQuestionUpdate(BaseModel):
    drive_url: Optional[HttpUrl] = None
    course_code: Optional[str] = Field(None, min_length=1, max_length=50)
    course_name: Optional[str] = Field(None, min_length=1, max_length=200)
    ct_no: Optional[int] = Field(None, ge=1, le=20)
