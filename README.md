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
