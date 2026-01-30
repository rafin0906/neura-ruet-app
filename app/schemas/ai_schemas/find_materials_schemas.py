from enum import Enum
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, ConfigDict, model_validator


class MaterialType(str, Enum):
    class_note = "class_note"
    ct_question = "ct_question"
    lecture_slide = "lecture_slide"
    semester_question = "semester_question"


class MatchMode(str, Enum):
    exact = "exact"
    contains = "contains"


class SortBy(str, Enum):
    newest = "newest"
    oldest = "oldest"


class QueryMode(str, Enum):
    query = "query"   # run DB query now
    ask = "ask"       # ask user for more info


class FindMaterialsLLMOutput(BaseModel):
    """
    STRICT output JSON the LLM must return for 'find_materials'.
    """

    model_config = ConfigDict(extra="forbid")

    tool: Literal["find_materials"] = "find_materials"

    # 🔑 decision field
    mode: QueryMode = QueryMode.query

    # used only when mode == "ask"
    question: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)

    # -------------------------
    # Filters (ALL optional)
    # -------------------------
    material_type: MaterialType

    course_code: Optional[str] = None
    course_name: Optional[str] = None

    dept: Optional[str] = None
    sec: Optional[str] = None
    series: Optional[str] = None

    # class_note / lecture_slide
    topic: Optional[str] = None

    # class_note only
    written_by: Optional[str] = None

    # ct_question only
    ct_no: Optional[int] = None

    # semester_question only
    year: Optional[int] = None

    # -------------------------
    # Query behavior
    # -------------------------
    match_mode: MatchMode = MatchMode.contains
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0)
    sort_by: SortBy = SortBy.newest

    confidence: float = Field(0.7, ge=0.0, le=1.0)

    
    @model_validator(mode="after")
    def enforce_field_rules(self):
        mt = self.material_type

        # ---- ct_question rules ----
        if mt == MaterialType.ct_question:
            # ct_question must NOT use fields for other types
            if self.topic is not None:
                raise ValueError("topic is not allowed for ct_question; use course_name or course_code instead")
            if self.written_by is not None:
                raise ValueError("written_by is not allowed for ct_question")
            if self.year is not None:
                raise ValueError("year is not allowed for ct_question")

        # ---- semester_question rules ----
        if mt == MaterialType.semester_question:
            if self.topic is not None:
                raise ValueError("topic is not allowed for semester_question")
            if self.written_by is not None:
                raise ValueError("written_by is not allowed for semester_question")
            if self.ct_no is not None:
                raise ValueError("ct_no is not allowed for semester_question")

        # ---- lecture_slide rules ----
        if mt == MaterialType.lecture_slide:
            if self.written_by is not None:
                raise ValueError("written_by is not allowed for lecture_slide")
            if self.ct_no is not None:
                raise ValueError("ct_no is not allowed for lecture_slide")
            if self.year is not None:
                raise ValueError("year is not allowed for lecture_slide")

        # ---- class_note rules ----
        if mt == MaterialType.class_note:
            if self.ct_no is not None:
                raise ValueError("ct_no is not allowed for class_note")
            if self.year is not None:
                raise ValueError("year is not allowed for class_note")

        # If mode=ask -> must have question
        if self.mode == QueryMode.ask and not self.question:
            raise ValueError("question is required when mode='ask'")

        return self
