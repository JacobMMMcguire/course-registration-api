import re
from typing import List

from bs4 import BeautifulSoup

from app.models import Course

COURSE_CODE_PATTERN = re.compile(r"[A-Z]{2,4}\s?\d{3,4}[A-Z]?")

# Matches catalog title lines such as:
#   "CPSC 1046. Introduction to Computer Science. 3 Credits."
TITLE_LINE_PATTERN = re.compile(
    r"^\s*([A-Z]{2,4}\s?\d{3,4}[A-Z]?)\.\s*(.+?)\.\s*([\d.]+(?:\s*-\s*[\d.]+)?)\s*Credits?\.?\s*$"
)

LABEL_STOP_PATTERN = re.compile(r"Prerequisite|Cross[- ]?listed|Corequisite", re.IGNORECASE)

# Splits a matched code into its letter and digit parts so "COSC1047" and
# "COSC 1047" both normalize to "COSC 1047" — otherwise the same course could
# appear under two different-looking strings depending on how a catalog
# happened to space it, which breaks exact-match lookups downstream.
CODE_PARTS_PATTERN = re.compile(r"([A-Z]{2,4})\s?(\d{3,4}[A-Z]?)")


def _normalize_code(code: str) -> str:
    match = CODE_PARTS_PATTERN.fullmatch(code.strip())
    if not match:
        return re.sub(r"\s+", " ", code).strip()
    return f"{match.group(1)} {match.group(2)}"


def _extract_codes(text: str) -> List[str]:
    """Pull every course-code-shaped token out of a free-text string,
    normalize spacing, and drop duplicates while preserving order.

    DESIGN DECISION (see docs/DECISIONS.md): this returns a flat list and
    does not preserve AND/OR logical grouping. "COSC 1046 and either
    COSC 1047 or ITEC 1047" becomes ["COSC 1046", "COSC 1047", "ITEC 1047"],
    which reads as "all three required" rather than "COSC 1046 AND (COSC 1047
    OR ITEC 1047)". This was a deliberate, temporary scope cut pending
    stakeholder input — do not silently change this shape without updating
    that doc and the /api/v1/admin/catalog/import response contract.
    """
    codes = [_normalize_code(code) for code in COURSE_CODE_PATTERN.findall(text)]
    return list(dict.fromkeys(codes))


def parse_catalog_html(html: str) -> List[Course]:
    """Extract Course Code, Title, Credits, Prerequisites, and Cross-listed
    courses from a course catalog HTML document.

    Catalogs are exported in different shapes (a table with header columns,
    or a repeated "courseblock" div per course), so both are supported. The
    layout is detected structurally — nothing about a specific course code
    or title is hardcoded.
    """
    soup = BeautifulSoup(html, "html.parser")

    courses = _parse_tables(soup)
    if not courses:
        courses = _parse_courseblocks(soup)

    return courses


def _parse_tables(soup: BeautifulSoup) -> List[Course]:
    courses: List[Course] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        header_cells = [cell.get_text(" ", strip=True).lower() for cell in rows[0].find_all(["th", "td"])]
        code_idx = _find_column(header_cells, "code")
        title_idx = _find_column(header_cells, "title")
        credits_idx = _find_column(header_cells, "credit")
        prereq_idx = _find_column(header_cells, "prerequisite")
        cross_idx = _find_column(header_cells, "cross")

        if code_idx is None or title_idx is None or credits_idx is None:
            continue

        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells or len(cells) <= max(code_idx, title_idx, credits_idx):
                continue

            code = cells[code_idx].get_text(" ", strip=True)
            if not COURSE_CODE_PATTERN.fullmatch(code):
                continue

            prereq_text = cells[prereq_idx].get_text(" ", strip=True) if prereq_idx is not None and prereq_idx < len(cells) else ""
            cross_text = cells[cross_idx].get_text(" ", strip=True) if cross_idx is not None and cross_idx < len(cells) else ""

            courses.append(
                Course(
                    course_code=_normalize_code(code),
                    title=cells[title_idx].get_text(" ", strip=True),
                    credits=cells[credits_idx].get_text(" ", strip=True),
                    prerequisites=_extract_codes(prereq_text),
                    cross_listed=_extract_codes(cross_text),
                )
            )

    return courses


def _find_column(headers: List[str], keyword: str) -> "int | None":
    for index, header in enumerate(headers):
        if keyword in header:
            return index
    return None


def _parse_courseblocks(soup: BeautifulSoup) -> List[Course]:
    blocks = soup.select(".courseblock")
    if not blocks:
        blocks = soup.select("[class*=course]")

    courses: List[Course] = []
    for block in blocks:
        title_el = block.select_one(".courseblocktitle") or block.find(
            ["h2", "h3", "h4", "strong"]
        )
        if title_el is None:
            continue

        match = TITLE_LINE_PATTERN.match(title_el.get_text(" ", strip=True))
        if not match:
            continue

        code_raw, title, credits = match.groups()
        block_text = block.get_text(" ", strip=True)

        courses.append(
            Course(
                course_code=_normalize_code(code_raw),
                title=title.strip(),
                credits=credits.strip(),
                prerequisites=_extract_codes_after_label(block_text, r"Prerequisite\(?s?\)?\s*:?"),
                cross_listed=_extract_codes_after_label(
                    block_text, r"Cross[- ]?listed(?:\s+with)?\s*:?"
                ),
            )
        )

    return courses


def _extract_codes_after_label(text: str, label_pattern: str) -> List[str]:
    label_match = re.search(label_pattern, text, re.IGNORECASE)
    if not label_match:
        return []

    remainder = text[label_match.end():]
    stop_match = LABEL_STOP_PATTERN.search(remainder)
    if stop_match:
        remainder = remainder[: stop_match.start()]

    return _extract_codes(remainder)
