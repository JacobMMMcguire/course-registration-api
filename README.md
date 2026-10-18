# Course Catalog API
An administrative API which securely ingests files, parses the DOM, and exposes clean data. Utilizes FastAPI.

# Setup

  1. Install Dependencies

      `pip install -r requirements.txt`

  2. Run the application

     `uvicorn main:app --reload`

     The API will be available at `http://localhost:8000`

# API Endpoints

Get Course by Code:
`GET /api/v1/catalog/courses/{course_code}`

Import Course Catalog:
`POST /api/v1/admin/catalog/import`

Accepts a `multipart/form-data` upload (field name `file`) containing a course
catalog HTML document. The file is streamed into memory in fixed-size chunks
(capped at 10 MB) rather than loaded in one shot, so an oversized upload is
rejected before the whole thing is buffered. The HTML DOM is then parsed to
extract each course's Code, Title, Credits, Prerequisites, and Cross-listed
courses, which replace the current in-memory catalog.

Example:
```
curl -X POST http://localhost:8000/api/v1/admin/catalog/import \
  -F "file=@sample_data/Course Catalog.html;type=text/html"
```

## Student Profile Endpoints

All routes are under `/api/v1/students/{student_id}`. A student is created by a
history import; every other route returns `404` for an unknown student.
Student data is kept in memory per `student_id` (see `app/student_storage.py`),
so run a single uvicorn worker.

| Method | Path | Body | Success |
|---|---|---|---|
| `POST` | `/history/import` | multipart `file` (HTML transcript) | `201` `{"status", "past_courses_imported"}` |
| `PUT` | `/history` | `{"history": [{course_code, term, credits_earned, status}]}` | `200` |
| `DELETE` | `/history` | — | `200` |
| `POST` | `/plan` | `{"planned_courses": [{course_code, term}]}` | `200` `{"status", "planned_courses_saved"}` |
| `PUT` | `/plan` | same as `POST` | `200` |
| `DELETE` | `/plan` | — | `200` |
| `GET` | `/profile` | — | `200` `{"student_id", "history", "plan"}` |

The transcript parser (`app/parsers/transcript_parser.py`) finds tables by their
`Status · Course · Grade · Term · Credits` header, keeps rows whose status is
Completed/In-Progress/Attempted with a non-empty term, and deduplicates by
`(course_code, term)`, preferring a numeric grade, then a letter grade, then the
higher credits.

Example:
```
curl -F "file=@student-example.html" http://localhost:8000/api/v1/students/111/history/import
curl http://localhost:8000/api/v1/students/111/profile
```
