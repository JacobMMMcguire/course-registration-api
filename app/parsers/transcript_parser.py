import re
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from app.models import PastCourse

PAST_STATUSES = {"Completed", "In-Progress", "Attempted"}

# Header cells (lowercased) that identify a transcript table. The title
# column has no fixed header text, so it isn't required.
REQUIRED_HEADERS = ("status", "course", "grade", "term", "credits")

NUMERIC_GRADE_PATTERN = re.compile(r"\d+(?:\.\d+)?")
LETTER_GRADE_PATTERN = re.compile(r"[A-EF][+-]?", re.IGNORECASE)


def _cell_text(cell: Tag) -> str:
    # Cell values are kept verbatim apart from trimming, per the canonical rule.
    return cell.get_text(" ", strip=True)


def _header_index(row: Tag) -> Optional[Dict[str, int]]:
    """Map each required header name to its column index, or None if this
    row isn't a transcript header row."""
    labels = [_cell_text(cell).lower() for cell in row.find_all(["th", "td"])]
    if not all(name in labels for name in REQUIRED_HEADERS):
        return None
    return {name: labels.index(name) for name in REQUIRED_HEADERS}


def _parse_credits(text: str) -> int:
    # A failed lab often shows a blank or non-numeric credits cell, which
    # counts as 0 earned rather than a parse error. Strict int() on purpose:
    # the canonical rule treats anything else (even "3.00") as non-numeric.
    try:
        return int(text)
    except ValueError:
        return 0


def _grade_rank(grade: str) -> Tuple[int, float]:
    """Numeric grade beats letter grade beats P/blank/other (W, IP, ...),
    and a higher numeric grade beats a lower one. Used to pick the most
    informative copy when a course repeats across requirement tables."""
    grade = grade.strip()
    if NUMERIC_GRADE_PATTERN.fullmatch(grade):
        return (2, float(grade))
    if LETTER_GRADE_PATTERN.fullmatch(grade):
        return (1, 0.0)
    return (0, 0.0)


def parse_transcript_html(html: str) -> List[PastCourse]:
    """Extract past courses from a student transcript export.

    The export repeats the same course under several requirement tables, and
    mixes in Fulfilled/Planned placeholder rows with no term. Tables are found
    by their header row and columns are located by header name, so nothing
    about a specific course code or column order is hardcoded.
    """
    soup = BeautifulSoup(html, "html.parser")

    # (course_code, term) -> (rank key, record), so duplicates collapse to the
    # row with the best grade, then the higher credits.
    best: Dict[Tuple[str, str], Tuple[Tuple[Tuple[int, float], int], PastCourse]] = {}

    for table in soup.find_all("table"):
        columns: Optional[Dict[str, int]] = None
        for row in table.find_all("tr"):
            # Nested tables are visited on their own; skip their rows here.
            if row.find_parent("table") is not table:
                continue

            if columns is None:
                columns = _header_index(row)
                continue

            cells = row.find_all(["td", "th"])
            if len(cells) <= max(columns.values()):
                continue
            values = {name: _cell_text(cells[idx]) for name, idx in columns.items()}

            if values["status"] not in PAST_STATUSES or not values["term"]:
                continue

            record = PastCourse(
                course_code=values["course"],
                term=values["term"],
                credits_earned=_parse_credits(values["credits"]),
                status=values["status"],
            )
            key = (record.course_code, record.term)
            rank = (_grade_rank(values["grade"]), record.credits_earned)
            if key not in best or rank > best[key][0]:
                best[key] = (rank, record)

    return [record for _, record in best.values()]
