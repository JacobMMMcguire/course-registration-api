import re
from typing import Dict, List, Optional

from app.models import Course

# In-memory course catalog. Replaced entirely on the next successful import,
# so re-uploading a catalog file simply refreshes the data set.
_courses: Dict[str, Course] = {}


def normalize_code(course_code: str) -> str:
    # "COSC 3506", "COSC-3506", and "cosc3506" must all resolve to the same
    # entry, since the catalog, transcript, and plan don't agree on spacing.
    return re.sub(r"[\s-]+", "", course_code).upper()


def replace_courses(courses: List[Course]) -> None:
    _courses.clear()
    for course in courses:
        _courses[normalize_code(course.course_code)] = course


def get_course(course_code: str) -> Optional[Course]:
    return _courses.get(normalize_code(course_code))


def get_all_courses() -> List[Course]:
    return list(_courses.values())
