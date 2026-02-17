# app/schemas/result_schemas.py
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional
from datetime import datetime
from uuid import UUID


def _normalize_course_code(value: str) -> str:
    if value is None:
        raise ValueError("course_code is required")
    cleaned = str(value).strip().upper()
    cleaned = cleaned.replace(" ", "").replace("_", "-")
    # Ensure a single hyphen between dept and number when possible
    if "-" not in cleaned and len(cleaned) >= 7:
        cleaned = f"{cleaned[:3]}-{cleaned[3:]}"
    return cleaned


def _normalize_section(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "" or cleaned.lower() in {"none", "null"}:
            return None
        cleaned_upper = cleaned.upper()
        if cleaned_upper in {"A", "B", "C"}:
            return cleaned_upper
    raise ValueError("Section must be A, B, C or None")


# -----------------------------
# Result Entry Schemas
# -----------------------------
class ResultEntryBase(BaseModel):
    roll_no: str = Field(..., min_length=1)
    marks: str = Field(..., description="Use numeric marks or 'A' for absent")

    @field_validator("marks")
    @classmethod
    def validate_marks(cls, v: str):
        v = v.strip().upper()

        if v == "A":
            return v

        if not v.isdigit():
            raise ValueError("marks must be a number or 'A' for absent")

        return v


class ResultEntryCreate(ResultEntryBase):
    pass


class ResultEntryResponse(ResultEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    result_sheet_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# -----------------------------
# Result Sheet Schemas
# -----------------------------
class ResultSheetBase(BaseModel):
    ct_no: int = Field(..., ge=1)
    course_code: str = Field(..., min_length=2, max_length=50)
    course_name: str = Field(..., min_length=2, max_length=120)

    dept: str = Field(..., min_length=2, max_length=20)
    section: Optional[str] = None
    series: int = Field(...)

    starting_roll: Optional[str] = None
    ending_roll: Optional[str] = None


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

    @field_validator("course_code")
    def validate_course_code(cls, value):
        return _normalize_course_code(value)

    @field_validator("series")
    def validate_series(cls, value):
        if value is None:
            return value
        if value < 19 or value > 25:
            raise ValueError("Series must be between 19 and 25")
        return value

    @field_validator("section")
    def validate_section(cls, value):
        return _normalize_section(value)


class ResultSheetCreate(ResultSheetBase):
    pass


class ResultSheetUpdate(BaseModel):
    ct_no: Optional[int] = Field(None, ge=1)
    course_code: Optional[str] = Field(None, min_length=2, max_length=50)
    course_name: Optional[str] = Field(None, min_length=2, max_length=120)

    dept: Optional[str] = Field(None, min_length=2, max_length=20)
    section: Optional[str] = None
    series: Optional[int] = None

    starting_roll: Optional[str] = None
    ending_roll: Optional[str] = None

    @field_validator("dept")
    @classmethod
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

    @field_validator("course_code")
    @classmethod
    def validate_course_code(cls, value):
        if value is None:
            return value
        return _normalize_course_code(value)

    @field_validator("series")
    @classmethod
    def validate_series(cls, value):
        if value is None:
            return value
        if value < 19 or value > 25:
            raise ValueError("Series must be between 19 and 25")
        return value

    @field_validator("section")
    @classmethod
    def validate_section(cls, value):
        return _normalize_section(value)


class ResultSheetResponse(ResultSheetBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by_teacher_id: Optional[UUID] = None
    title: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# -----------------------------
# Batch Upload
# -----------------------------
class ResultSheetBatchUpload(BaseModel):
    entries: List[ResultEntryCreate]

    @field_validator("entries")
    @classmethod
    def validate_entries_not_empty(cls, v):
        if not v:
            raise ValueError("entries cannot be empty")
        return v


class ResultSheetWithEntriesResponse(ResultSheetResponse):
    entries: List[ResultEntryResponse] = []


class ResultSheetHistoryItem(BaseModel):
    id: UUID
    title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
