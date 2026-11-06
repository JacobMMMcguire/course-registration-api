from typing import List, Union

from pydantic import BaseModel, Field


class Course(BaseModel):
    course_code: str
    title: str
    credits: str
    prerequisites: List[str] = Field(default_factory=list)
    cross_listed: List[str] = Field(default_factory=list)


class ImportResult(BaseModel):
    imported_count: int
    course_codes: List[str]


class PastCourse(BaseModel):
    course_code: str
    term: str
    credits_earned: int
    status: str


class PlannedCourse(BaseModel):
    course_code: str
    term: str


class HistoryUpdate(BaseModel):
    history: List[PastCourse]


class PlanUpdate(BaseModel):
    planned_courses: List[PlannedCourse]


class StudentProfile(BaseModel):
    student_id: str
    history: List[PastCourse]
    plan: List[PlannedCourse]


class AuditIssue(BaseModel):
    course_code: str
    type: str
    message: str


class TermValidation(BaseModel):
    term: str
    errors: List[AuditIssue]


class CreditSummary(BaseModel):
    # int | float so whole credit counts serialize as 90, not 90.0.
    total_earned: Union[int, float]
    total_planned: Union[int, float]
    total_remaining_for_graduation: Union[int, float]


class AuditReport(BaseModel):
    student_id: str
    status: str
    timeline_validation: List[TermValidation]
    cross_list_violations: List[AuditIssue]
    credit_summary: CreditSummary
