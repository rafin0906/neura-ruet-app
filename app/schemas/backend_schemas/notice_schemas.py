from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class TeacherNoticeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    notice_message: str = Field(..., min_length=1)

    dept: str
    sec: str
    series: str


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