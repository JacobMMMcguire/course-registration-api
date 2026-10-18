from threading import Lock
from typing import Dict, List, Optional

from app.models import PastCourse, PlannedCourse, StudentProfile

# In-memory student records keyed by student_id. Every student gets its own
# lists, and records are copied on the way in and out, so one student's data
# can never alias another's. Routers go through these functions only, so a
# real database can replace this module later without touching them.
_students: Dict[str, Dict[str, list]] = {}
_lock = Lock()


def _copy(items: list) -> list:
    return [item.model_copy() for item in items]


def exists(student_id: str) -> bool:
    return student_id in _students


def import_history(student_id: str, history: List[PastCourse]) -> None:
    """Create the student if needed and replace their history. An existing
    plan is kept, since a re-import only refreshes past courses."""
    with _lock:
        record = _students.setdefault(student_id, {"history": [], "plan": []})
        record["history"] = _copy(history)


def replace_history(student_id: str, history: List[PastCourse]) -> bool:
    with _lock:
        if student_id not in _students:
            return False
        _students[student_id]["history"] = _copy(history)
        return True


def replace_plan(student_id: str, plan: List[PlannedCourse]) -> bool:
    with _lock:
        if student_id not in _students:
            return False
        _students[student_id]["plan"] = _copy(plan)
        return True


def get_profile(student_id: str) -> Optional[StudentProfile]:
    with _lock:
        record = _students.get(student_id)
        if record is None:
            return None
        return StudentProfile(
            student_id=student_id,
            history=_copy(record["history"]),
            plan=_copy(record["plan"]),
        )
