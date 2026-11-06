import pytest

from app.audit import (
    CROSS_LIST_CONFLICT,
    MISSING_PREREQUISITE,
    build_audit_report,
    catalog_credits,
    display_code,
    term_key,
    total_earned,
)
from app.models import Course, PastCourse, PlannedCourse, StudentProfile
from app.storage import normalize_code

CATALOG = {
    normalize_code(c.course_code): c
    for c in [
        Course(course_code="COSC 2006", title="DS", credits="3"),
        Course(course_code="COSC 3127", title="PL", credits="3", prerequisites=["COSC 2006"]),
        Course(course_code="COSC 4426", title="Topics", credits="3", prerequisites=["COSC 3127", "COSC 2006"]),
        Course(course_code="COSC 3506", title="SE", credits="3", cross_listed=["ITEC 3506"]),
        # One-sided listing: only ITEC 2000 names its partner.
        Course(course_code="ITEC 2000", title="One-sided", credits="3", cross_listed=["COSC 2000"]),
        Course(course_code="COSC 2000", title="One-sided", credits="3"),
        Course(course_code="ITEC 3506", title="SE", credits="3"),
        Course(course_code="LABS 1000", title="Lab", credits="1.5"),
        Course(course_code="VARI 1000", title="Variable", credits="3-6"),
    ]
}


def lookup(code):
    return CATALOG.get(normalize_code(code))


def past(code, term, credits=3, status="Completed"):
    return PastCourse(course_code=code, term=term, credits_earned=credits, status=status)


def plan(code, term):
    return PlannedCourse(course_code=code, term=term)


def report(history, planned, strict=False):
    profile = StudentProfile(student_id="1", history=history, plan=planned)
    return build_audit_report(profile, lookup, strict=strict)


def test_term_ordering():
    terms = ["26F", "24W", "26SP", "23F", "24F", "26S", "26W"]
    assert sorted(terms, key=term_key) == ["23F", "24W", "24F", "26W", "26SP", "26S", "26F"]


def test_term_ordering_is_case_insensitive_and_accepts_four_digit_years():
    assert term_key("26sp") == term_key("26SP") == term_key("2026SP")


def test_unparseable_term_sorts_last():
    assert term_key("bogus") > term_key("99F")


@pytest.mark.parametrize("code", ["COSC 3506", "COSC-3506", "cosc3506", " cosc - 3506 "])
def test_codes_are_format_insensitive(code):
    assert normalize_code(code) == "COSC3506"
    assert display_code(code) == "COSC-3506"


def test_display_code_leaves_unusual_codes_alone():
    assert display_code("abc") == "ABC"


def test_catalog_credits():
    assert catalog_credits(lookup("COSC 2006")) == 3
    assert catalog_credits(lookup("LABS 1000")) == 1.5
    assert catalog_credits(lookup("VARI 1000")) == 3
    assert catalog_credits(None) == 0
    assert catalog_credits(Course(course_code="X 1", title="", credits="TBD")) == 0


def test_no_issues_is_ok_even_when_strict():
    result = report([past("COSC 2006", "24F")], [plan("COSC 3127", "25W")], strict=True)
    assert result.status == "ok"
    assert result.timeline_validation == []
    assert result.cross_list_violations == []


def test_missing_prerequisite():
    result = report([], [plan("COSC 3127", "25W")])
    assert result.status == "warning"
    [term] = result.timeline_validation
    assert term.term == "25W"
    [error] = term.errors
    assert error.type == MISSING_PREREQUISITE
    assert error.course_code == "COSC-3127"
    assert error.message == "Missing prerequisite: COSC-2006"


def test_strict_turns_issues_into_failed():
    assert report([], [plan("COSC 3127", "25W")], strict=True).status == "failed"


def test_prerequisite_must_be_strictly_earlier():
    same_term = report([past("COSC 2006", "25W")], [plan("COSC 3127", "25W")])
    later = report([past("COSC 2006", "25F")], [plan("COSC 3127", "25W")])
    assert same_term.timeline_validation and later.timeline_validation


def test_season_order_matters_within_a_year():
    # 26SP comes before 26F, but 26F does not come before 26SP.
    assert report([past("COSC 2006", "26SP")], [plan("COSC 3127", "26F")]).status == "ok"
    assert report([past("COSC 2006", "26F")], [plan("COSC 3127", "26SP")]).status == "warning"


def test_non_completed_prerequisite_does_not_count():
    for status in ("In-Progress", "Attempted"):
        result = report([past("COSC 2006", "24F", status=status)], [plan("COSC 3127", "25W")])
        assert result.timeline_validation


def test_planned_prerequisite_does_not_count():
    result = report([], [plan("COSC 2006", "25W"), plan("COSC 3127", "25F")])
    assert [t.term for t in result.timeline_validation] == ["25F"]


def test_each_missing_prerequisite_is_reported():
    result = report([], [plan("COSC 4426", "26F")])
    messages = [e.message for e in result.timeline_validation[0].errors]
    assert messages == ["Missing prerequisite: COSC-3127", "Missing prerequisite: COSC-2006"]


def test_timeline_is_chronological_and_grouped_by_term():
    planned = [plan("COSC 4426", "26F"), plan("COSC 3127", "24W"), plan("COSC 3127", "26SP")]
    result = report([], planned)
    assert [t.term for t in result.timeline_validation] == ["24W", "26SP", "26F"]


def test_matching_ignores_code_format():
    result = report([past("cosc-2006", "24F")], [plan("cosc3127", "25W")])
    assert result.status == "ok"


def test_cross_list_conflict():
    result = report([past("COSC-3506", "25F")], [plan("itec 3506", "26F")])
    [violation] = result.cross_list_violations
    assert violation.type == CROSS_LIST_CONFLICT
    assert violation.course_code == "ITEC-3506"
    assert violation.message == "Cross-listed with completed course COSC-3506"
    assert result.status == "warning"


def test_cross_list_listed_only_on_completed_course():
    result = report([past("ITEC 2000", "25F")], [plan("COSC 2000", "26F")])
    assert [v.message for v in result.cross_list_violations] == ["Cross-listed with completed course ITEC-2000"]


def test_cross_list_partner_not_completed_is_fine():
    in_progress = past("COSC 3506", "26W", status="In-Progress")
    assert report([in_progress], [plan("COSC 3506", "26F")]).cross_list_violations == []
    assert report([in_progress], [plan("ITEC 3506", "26F")]).cross_list_violations == []


def test_retake_counts_once():
    history = [
        past("COSC 2006", "24W", credits=0, status="Attempted"),
        past("COSC 2006", "24F", credits=3),
        past("COSC-2006", "25W", credits=3),
        past("COSC 3127", "25W", credits=3, status="In-Progress"),
    ]
    assert total_earned(history) == 3


def test_later_pass_overrides_earlier_failure():
    history = [past("COSC 2006", "24W", credits=0), past("COSC 2006", "24F", credits=3)]
    assert total_earned(history) == 3


def test_credit_summary():
    history = [past(f"HIST {1000 + i}", "24F") for i in range(30)]  # 90 credits
    planned = [plan("COSC 2006", "26F"), plan("COSC 3506", "26F"), plan("LABS 1000", "26F"), plan("NOPE 9999", "26F")]
    summary = report(history, planned).credit_summary
    assert summary.total_earned == 90
    assert summary.total_planned == 7.5
    assert summary.total_remaining_for_graduation == 22.5


def test_remaining_never_goes_negative():
    history = [past(f"HIST {1000 + i}", "24F") for i in range(45)]
    assert report(history, []).credit_summary.total_remaining_for_graduation == 0
