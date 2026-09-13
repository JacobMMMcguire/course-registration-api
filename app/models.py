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
