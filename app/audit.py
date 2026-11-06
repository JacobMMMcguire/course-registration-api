import re
from typing import Callable, Dict, List, Optional, Tuple

from app.models import (
    AuditIssue,
    AuditReport,
    Course,
    CreditSummary,
    PastCourse,
    PlannedCourse,
    StudentProfile,
    TermValidation,
)
from app.storage import normalize_code

GRADUATION_CREDITS = 120

MISSING_PREREQUISITE = "MISSING_PREREQUISITE"
CROSS_LIST_CONFLICT = "CROSS_LIST_CONFLICT"

SEASON_ORDER = {"W": 0, "SP": 1, "S": 2, "F": 3}

# "26SP", "24W", "2025F" -> year digits + season. SP is listed before S so the
# alternation doesn't stop at the "S" of "SP".
TERM_PATTERN = re.compile(r"^\s*(\d{2}|\d{4})\s*(SP|W|S|F)\s*$", re.IGNORECASE)
CODE_PARTS_PATTERN = re.compile(r"^([A-Z]+)(\d.*)$")
CREDITS_PATTERN = re.compile(r"\d+(?:\.\d+)?")

CourseLookup = Callable[[str], Optional[Course]]


def term_key(term: str) -> Tuple[int, int, str]:
    """Sort key for a term: year, then season (W < SP < S < F). Unparseable
    terms sort after every real term instead of raising, so one bad row can't
    break the whole report."""
    match = TERM_PATTERN.match(term)
    if not match:
        return (10_000, 0, term)
    year = int(match.group(1)) % 100
    return (year, SEASON_ORDER[match.group(2).upper()], "")


def display_code(course_code: str) -> str:
    # One display form for every code in the report ("COSC-3506"), whatever
    # spacing the catalog, transcript, or plan used.
    code = normalize_code(course_code)
    match = CODE_PARTS_PATTERN.match(code)
    return f"{match.group(1)}-{match.group(2)}" if match else code


def _number(value: float) -> float:
    # Whole credit counts come back as ints so the JSON reads 90, not 90.0.
    return int(value) if float(value).is_integer() else value


def catalog_credits(course: Optional[Course]) -> float:
    """Credits from the catalog's free-text field. A range such as "3-6"
    counts as its first value; a course missing from the catalog counts 0."""
    if course is None:
        return 0
    match = CREDITS_PATTERN.search(course.credits)
    return float(match.group()) if match else 0


def _is_completed(entry: PastCourse) -> bool:
    return entry.status.strip().lower() == "completed"


def completed_terms(history: List[PastCourse]) -> Dict[str, List[str]]:
    """Normalized course code -> every term it was Completed in."""
    terms: Dict[str, List[str]] = {}
    for entry in history:
        if _is_completed(entry):
            terms.setdefault(normalize_code(entry.course_code), []).append(entry.term)
    return terms


def total_earned(history: List[PastCourse]) -> float:
    """Each course counts once, however many times it was taken. Attempts that
    weren't Completed contribute 0, and among Completed attempts the best one
    wins, so a later pass overrides an earlier failure."""
    best: Dict[str, int] = {}
    for entry in history:
        if not _is_completed(entry):
            continue
        code = normalize_code(entry.course_code)
        best[code] = max(best.get(code, 0), entry.credits_earned)
    return sum(best.values())


def _missing_prerequisites(
    planned: PlannedCourse, course: Optional[Course], completed: Dict[str, List[str]]
) -> List[AuditIssue]:
    # Every listed prerequisite is treated as required (see docs/DECISIONS.md),
    # and only a completion in a strictly earlier term satisfies it.
    if course is None:
        return []
    planned_key = term_key(planned.term)
    issues = []
    for prereq in course.prerequisites:
        terms = completed.get(normalize_code(prereq), [])
        if not any(term_key(term) < planned_key for term in terms):
            issues.append(
                AuditIssue(
                    course_code=display_code(planned.course_code),
                    type=MISSING_PREREQUISITE,
                    message=f"Missing prerequisite: {display_code(prereq)}",
                )
            )
    return issues


def _cross_list_conflicts(
    planned: PlannedCourse,
    course: Optional[Course],
    completed: Dict[str, List[str]],
    lookup: CourseLookup,
) -> List[AuditIssue]:
    planned_code = normalize_code(planned.course_code)
    partners = {normalize_code(code) for code in course.cross_listed} if course else set()
    # Also honour a listing that only appears on the completed course's side,
    # since catalogs don't always record cross-listings symmetrically.
    for code in completed:
        other = lookup(code)
        if other and planned_code in {normalize_code(c) for c in other.cross_listed}:
            partners.add(code)
    partners.discard(planned_code)

    return [
        AuditIssue(
            course_code=display_code(planned.course_code),
            type=CROSS_LIST_CONFLICT,
            message=f"Cross-listed with completed course {display_code(code)}",
        )
        for code in sorted(partners)
        if code in completed
    ]


def build_audit_report(profile: StudentProfile, lookup: CourseLookup, strict: bool = False) -> AuditReport:
    completed = completed_terms(profile.history)

    errors_by_term: Dict[str, List[AuditIssue]] = {}
    cross_list_violations: List[AuditIssue] = []
    planned_credits = 0.0

    for planned in profile.plan:
        course = lookup(planned.course_code)
        planned_credits += catalog_credits(course)

        missing = _missing_prerequisites(planned, course, completed)
        if missing:
            errors_by_term.setdefault(planned.term, []).extend(missing)
        cross_list_violations.extend(_cross_list_conflicts(planned, course, completed, lookup))

    timeline = [
        TermValidation(term=term, errors=errors)
        for term, errors in sorted(errors_by_term.items(), key=lambda item: term_key(item[0]))
    ]

    if not timeline and not cross_list_violations:
        status = "ok"
    else:
        status = "failed" if strict else "warning"

    earned = total_earned(profile.history)
    return AuditReport(
        student_id=profile.student_id,
        status=status,
        timeline_validation=timeline,
        cross_list_violations=cross_list_violations,
        credit_summary=CreditSummary(
            total_earned=_number(earned),
            total_planned=_number(planned_credits),
            total_remaining_for_graduation=_number(max(0, GRADUATION_CREDITS - earned - planned_credits)),
        ),
    )
