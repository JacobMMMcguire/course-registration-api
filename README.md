# Course Catalog API
An administrative API which securely ingests files, parses the DOM, and exposes clean data. Utilizes FastAPI.

# Setup

  1. Install Dependencies

      `pip install -r requirements.txt`

  2. Run the application

     The API will be available at `http://localhost:8000`

# API Endpoint

Get Course by Code:
`GET /api/v1/catalog/courses/{course_code}`
