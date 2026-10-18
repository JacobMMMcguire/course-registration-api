from typing import List

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
