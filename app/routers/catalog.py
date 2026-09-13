from fastapi import APIRouter, HTTPException

from app import storage
from app.models import Course

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/courses/{course_code}", response_model=Course)
def get_course_by_code(course_code: str) -> Course:
    course = storage.get_course(course_code)
    if course is None:
        raise HTTPException(status_code=404, detail=f"Course '{course_code}' not found")
    return course
