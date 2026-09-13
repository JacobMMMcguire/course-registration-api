from fastapi import APIRouter, File, HTTPException, UploadFile

from app import storage
from app.models import ImportResult
from app.parsers.catalog_parser import parse_catalog_html

router = APIRouter(prefix="/api/v1/admin/catalog", tags=["admin"])

# Read the upload in fixed-size chunks rather than one large await file.read(),
# so a huge catalog file can't spike server memory before we even know its size.
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB


@router.post("/import", response_model=ImportResult)
async def import_catalog(file: UploadFile = File(...)) -> ImportResult:
    if not file.filename or not file.filename.lower().endswith((".html", ".htm")):
        raise HTTPException(status_code=400, detail="Uploaded file must be an HTML document (.html/.htm)")

    raw = bytearray()
    total_size = 0
    while chunk := await file.read(CHUNK_SIZE):
        total_size += len(chunk)
        if total_size > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds maximum allowed size of 10 MB")
        raw.extend(chunk)
    await file.close()

    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        html_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        html_text = raw.decode("latin-1")

    courses = parse_catalog_html(html_text)
    if not courses:
        raise HTTPException(status_code=422, detail="No courses could be parsed from the uploaded file")

    storage.replace_courses(courses)

    return ImportResult(
        imported_count=len(courses),
        course_codes=[course.course_code for course in courses],
    )
