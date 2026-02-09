from pydantic import BaseModel, Field

class BaseCoverExtracted(BaseModel):
    cover_type_no: str = Field(default="")
    cover_type_title: str = Field(default="")
    course_code: str = Field(default="")
    course_title: str = Field(default="")
    date_of_exp: str = Field(default="")
    date_of_submission: str = Field(default="")
    session: str = Field(default="")
    teacher_name: str = Field(default="")
    teacher_designation: str = Field(default="")
    teacher_dept: str = Field(default="")

class LabReportCoverInfoExtracted(BaseCoverExtracted):
    pass

class AssignmentCoverInfoExtracted(BaseCoverExtracted):
    pass

class ReportCoverInfoExtracted(BaseCoverExtracted):
    pass
