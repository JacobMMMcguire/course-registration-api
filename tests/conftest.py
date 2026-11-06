import pytest
from fastapi.testclient import TestClient

from app import storage, student_storage
from main import app

# Small catalog in the table layout the catalog parser accepts. Codes are
# spaced differently on purpose to exercise format-insensitive matching.
CATALOG_HTML = """
<html><body><table>
  <tr><th>Course Code</th><th>Title</th><th>Credits</th><th>Prerequisites</th><th>Cross-listed</th></tr>
  <tr><td>COSC 1046</td><td>Intro to CS I</td><td>3</td><td></td><td></td></tr>
  <tr><td>COSC 1047</td><td>Intro to CS II</td><td>3</td><td>COSC 1046</td><td></td></tr>
  <tr><td>COSC 2006</td><td>Data Structures</td><td>3</td><td>COSC 1047</td><td></td></tr>
  <tr><td>COSC 3127</td><td>Programming Languages</td><td>3</td><td>COSC 2006</td><td></td></tr>
  <tr><td>COSC 3506</td><td>Software Engineering</td><td>3</td><td>COSC 2006</td><td>ITEC 3506</td></tr>
  <tr><td>ITEC 3506</td><td>Software Engineering</td><td>3</td><td>COSC 2006</td><td>COSC 3506</td></tr>
  <tr><td>COSC 4426</td><td>Topics</td><td>3</td><td>COSC 3127</td><td></td></tr>
  <tr><td>MATH 1056</td><td>Discrete Math</td><td>3</td><td></td><td></td></tr>
</table></body></html>
"""

TRANSCRIPT_HTML = """
<html><body><table>
  <tr><th>Status</th><th>Course</th><th>Title</th><th>Grade</th><th>Term</th><th>Credits</th></tr>
  <tr><td>Completed</td><td>COSC-1046</td><td>Intro I</td><td>85</td><td>23F</td><td>3</td></tr>
  <tr><td>Completed</td><td>COSC-1047</td><td>Intro II</td><td>80</td><td>24W</td><td>3</td></tr>
  <tr><td>Attempted</td><td>COSC-2006</td><td>DS</td><td>40</td><td>24F</td><td></td></tr>
  <tr><td>Completed</td><td>COSC-2006</td><td>DS</td><td>75</td><td>25W</td><td>3</td></tr>
  <tr><td>Completed</td><td>COSC-3506</td><td>SE</td><td>90</td><td>25F</td><td>3</td></tr>
  <tr><td>In-Progress</td><td>MATH-1056</td><td>Discrete</td><td></td><td>26W</td><td>3</td></tr>
  <tr><td>Planned</td><td>COSC-3127</td><td>PL</td><td></td><td></td><td>3</td></tr>
</table></body></html>
"""


@pytest.fixture(autouse=True)
def clean_storage():
    storage.replace_courses([])
    student_storage._students.clear()
    yield
    storage.replace_courses([])
    student_storage._students.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def loaded_client(client):
    """A client with the catalog and student 770001's transcript imported."""
    response = client.post(
        "/api/v1/admin/catalog/import",
        files={"file": ("catalog.html", CATALOG_HTML, "text/html")},
    )
    assert response.status_code == 200
    response = client.post(
        "/api/v1/students/770001/history/import",
        files={"file": ("transcript.html", TRANSCRIPT_HTML, "text/html")},
    )
    assert response.status_code == 201
    return client
