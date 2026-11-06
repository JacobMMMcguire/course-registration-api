"""End-to-end tests against a running server, e.g. one booted by CI:

    uvicorn main:app --port 8000 &
    API_BASE_URL=http://127.0.0.1:8000 pytest tests/integration

Skipped when API_BASE_URL isn't set, so the unit suite runs on its own.
"""

import os
import uuid

import httpx
import pytest

from tests.conftest import CATALOG_HTML, TRANSCRIPT_HTML

BASE_URL = os.environ.get("API_BASE_URL")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="API_BASE_URL not set")


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        yield client


@pytest.fixture
def student(http):
    # A fresh id per test, since the live server keeps state between requests.
    student_id = f"it-{uuid.uuid4().hex[:8]}"
    response = http.post(
        "/api/v1/admin/catalog/import", files={"file": ("catalog.html", CATALOG_HTML, "text/html")}
    )
    assert response.status_code == 200
    response = http.post(
        f"/api/v1/students/{student_id}/history/import",
        files={"file": ("transcript.html", TRANSCRIPT_HTML, "text/html")},
    )
    assert response.status_code == 201
    return student_id


def test_catalog_lookup_is_format_insensitive(http, student):
    assert http.get("/api/v1/catalog/courses/cosc-3506").status_code == 200


def test_audit_report_end_to_end(http, student):
    planned = [
        {"course_code": "COSC-4426", "term": "26F"},
        {"course_code": "ITEC 3506", "term": "26F"},
    ]
    assert http.post(f"/api/v1/students/{student}/plan", json={"planned_courses": planned}).status_code == 200

    body = http.get(f"/api/v1/students/{student}/audit-report").json()
    assert body["student_id"] == student
    assert body["status"] == "warning"
    assert body["timeline_validation"][0]["term"] == "26F"
    assert body["timeline_validation"][0]["errors"][0]["type"] == "MISSING_PREREQUISITE"
    assert body["cross_list_violations"][0]["type"] == "CROSS_LIST_CONFLICT"
    assert body["credit_summary"] == {"total_earned": 12, "total_planned": 6, "total_remaining_for_graduation": 102}

    strict = http.get(f"/api/v1/students/{student}/audit-report", params={"strict": "true"}).json()
    assert strict["status"] == "failed"


def test_unknown_student_audit_is_404(http):
    assert http.get("/api/v1/students/does-not-exist/audit-report").status_code == 404
