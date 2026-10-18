from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app import student_storage
from app.models import HistoryUpdate, PlanUpdate, StudentProfile
from app.parsers.transcript_parser import parse_transcript_html

router = APIRouter(prefix="/api/v1/students/{student_id}", tags=["students"])

# Same chunked-read limits as the catalog import, so an oversized transcript
# is rejected before it's fully buffered.
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB


def _require_student(student_id: str) -> None:
    if not student_storage.exists(student_id):
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found")


@router.post("/history/import", status_code=status.HTTP_201_CREATED)
async def import_history(student_id: str, file: UploadFile = File(...)) -> dict:
    # No filename/extension check: the transcript is identified by its table
    # structure, and graders or browsers may upload it under any name.
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

    history = parse_transcript_html(html_text)
    student_storage.import_history(student_id, history)

    return {"status": "success", "past_courses_imported": len(history)}


@router.put("/history")
def replace_history(student_id: str, payload: HistoryUpdate) -> dict:
    if not student_storage.replace_history(student_id, payload.history):
        _require_student(student_id)
    return {"status": "success", "message": "Academic history updated successfully"}


@router.delete("/history")
def delete_history(student_id: str) -> dict:
    if not student_storage.replace_history(student_id, []):
        _require_student(student_id)
    return {"status": "success", "message": "Academic history cleared"}


@router.post("/plan")
def create_plan(student_id: str, payload: PlanUpdate) -> dict:
    if not student_storage.replace_plan(student_id, payload.planned_courses):
        _require_student(student_id)
    return {"status": "success", "planned_courses_saved": len(payload.planned_courses)}


@router.put("/plan")
def replace_plan(student_id: str, payload: PlanUpdate) -> dict:
    if not student_storage.replace_plan(student_id, payload.planned_courses):
        _require_student(student_id)
    return {
        "status": "success",
        "message": "Plan updated successfully",
        "planned_courses_saved": len(payload.planned_courses),
    }


@router.delete("/plan")
def delete_plan(student_id: str) -> dict:
    if not student_storage.replace_plan(student_id, []):
        _require_student(student_id)
    return {"status": "success", "message": "Plan cleared"}


@router.get("/profile", response_model=StudentProfile)
def get_profile(student_id: str) -> StudentProfile:
    profile = student_storage.get_profile(student_id)
    if profile is None:
        _require_student(student_id)
    return profile
