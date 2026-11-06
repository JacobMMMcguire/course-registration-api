from app.parsers.catalog_parser import parse_catalog_html

AUDIT = "/api/v1/students/770001/audit-report"
PLAN = "/api/v1/students/770001/plan"


def test_catalog_import_and_lookup(loaded_client):
    response = loaded_client.get("/api/v1/catalog/courses/cosc-3506")
    assert response.status_code == 200
    assert response.json()["cross_listed"] == ["ITEC 3506"]
    assert loaded_client.get("/api/v1/catalog/courses/NOPE 1000").status_code == 404


def test_catalog_import_rejects_bad_uploads(client):
    url = "/api/v1/admin/catalog/import"
    assert client.post(url, files={"file": ("c.txt", "x", "text/plain")}).status_code == 400
    assert client.post(url, files={"file": ("c.html", "", "text/html")}).status_code == 400
    assert client.post(url, files={"file": ("c.html", "<p>none</p>", "text/html")}).status_code == 422


def test_catalog_table_with_hyphenated_codes():
    html = """
    <table>
      <tr><th>Course Code</th><th>Title</th><th>Credits</th><th>Prerequisites</th><th>Cross-listed</th></tr>
      <tr><td>COSC-4426</td><td>Capstone</td><td>3</td><td>COSC-3127</td><td></td></tr>
      <tr><td>ITEC-3506</td><td>Web Systems</td><td>3</td><td>None</td><td>COSC-3506</td></tr>
    </table>
    """
    capstone, web = parse_catalog_html(html)
    assert capstone.course_code == "COSC 4426"
    assert capstone.prerequisites == ["COSC 3127"]
    assert web.prerequisites == []
    assert web.cross_listed == ["COSC 3506"]


def test_catalog_courseblock_layout():
    html = """
    <div class="courseblock">
      <p class="courseblocktitle">COSC 3506. Software Engineering. 3 Credits.</p>
      <p>Prerequisite: COSC 2006. Cross-listed with ITEC 3506.</p>
    </div>
    """
    [course] = parse_catalog_html(html)
    assert course.course_code == "COSC 3506"
    assert course.prerequisites == ["COSC 2006"]
    assert course.cross_listed == ["ITEC 3506"]


def test_history_import_skips_planned_rows(loaded_client):
    profile = loaded_client.get("/api/v1/students/770001/profile").json()
    assert {(h["course_code"], h["term"]) for h in profile["history"]} >= {("COSC-2006", "24F"), ("COSC-2006", "25W")}
    assert all(h["status"] != "Planned" for h in profile["history"])


def test_history_and_plan_crud(loaded_client):
    base = "/api/v1/students/770001"
    history = {"history": [{"course_code": "COSC 1046", "term": "23F", "credits_earned": 3, "status": "Completed"}]}
    assert loaded_client.put(f"{base}/history", json=history).status_code == 200
    planned = {"planned_courses": [{"course_code": "COSC 1047", "term": "24W"}]}
    assert loaded_client.put(f"{base}/plan", json=planned).json()["planned_courses_saved"] == 1

    profile = loaded_client.get(f"{base}/profile").json()
    assert len(profile["history"]) == 1 and len(profile["plan"]) == 1

    assert loaded_client.delete(f"{base}/history").status_code == 200
    assert loaded_client.delete(f"{base}/plan").status_code == 200
    profile = loaded_client.get(f"{base}/profile").json()
    assert profile["history"] == [] and profile["plan"] == []


def test_unknown_student_is_404(client):
    base = "/api/v1/students/nobody"
    assert client.get(f"{base}/profile").status_code == 404
    assert client.get(f"{base}/audit-report").status_code == 404
    assert client.post(f"{base}/plan", json={"planned_courses": []}).status_code == 404
    assert client.put(f"{base}/plan", json={"planned_courses": []}).status_code == 404
    assert client.delete(f"{base}/plan").status_code == 404
    assert client.put(f"{base}/history", json={"history": []}).status_code == 404
    assert client.delete(f"{base}/history").status_code == 404


def test_empty_transcript_upload_is_rejected(client):
    response = client.post("/api/v1/students/1/history/import", files={"file": ("t.html", "", "text/html")})
    assert response.status_code == 400


def test_audit_report_schema(loaded_client):
    loaded_client.post(PLAN, json={"planned_courses": [{"course_code": "COSC-4426", "term": "26F"}]})
    body = loaded_client.get(AUDIT).json()
    assert set(body) == {"student_id", "status", "timeline_validation", "cross_list_violations", "credit_summary"}
    assert body["student_id"] == "770001"
    assert set(body["credit_summary"]) == {"total_earned", "total_planned", "total_remaining_for_graduation"}


def test_audit_report_full_scenario(loaded_client):
    planned = [
        {"course_code": "COSC-4426", "term": "26F"},  # COSC 3127 never completed
        {"course_code": "ITEC 3506", "term": "26F"},  # cross-listed with completed COSC 3506
        {"course_code": "cosc3127", "term": "26W"},  # COSC 2006 passed in 25W: fine
        {"course_code": "COSC 2006", "term": "24W"},  # COSC 1047 completed 24W: same term, too late
    ]
    loaded_client.post(PLAN, json={"planned_courses": planned})
    body = loaded_client.get(AUDIT).json()

    assert body["status"] == "warning"
    assert [t["term"] for t in body["timeline_validation"]] == ["24W", "26F"]
    assert body["timeline_validation"][1]["errors"] == [
        {"course_code": "COSC-4426", "type": "MISSING_PREREQUISITE", "message": "Missing prerequisite: COSC-3127"}
    ]
    assert body["cross_list_violations"] == [
        {
            "course_code": "ITEC-3506",
            "type": "CROSS_LIST_CONFLICT",
            "message": "Cross-listed with completed course COSC-3506",
        }
    ]
    # 1046 + 1047 + 2006 (retake counted once) + 3506; the in-progress course earns nothing.
    assert body["credit_summary"] == {"total_earned": 12, "total_planned": 12, "total_remaining_for_graduation": 96}


def test_audit_report_strict(loaded_client):
    loaded_client.post(PLAN, json={"planned_courses": [{"course_code": "COSC-4426", "term": "26F"}]})
    assert loaded_client.get(AUDIT, params={"strict": "true"}).json()["status"] == "failed"
    assert loaded_client.get(AUDIT, params={"strict": "false"}).json()["status"] == "warning"


def test_audit_report_ok(loaded_client):
    loaded_client.post(PLAN, json={"planned_courses": [{"course_code": "COSC 3127", "term": "26F"}]})
    assert loaded_client.get(AUDIT, params={"strict": "true"}).json()["status"] == "ok"
