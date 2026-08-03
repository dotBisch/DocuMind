"""POST /documents/upload — HTTP concerns only; the pipeline does the work."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.db.client import get_client
from app.ingestion.loader import SUPPORTED_EXTENSIONS, UnsupportedFileType
from app.ingestion.pipeline import EmptyDocument, ingest_file
from app.models.schemas import UploadResponse

router = APIRouter()


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile,
    session_id: str | None = Form(default=None),
) -> UploadResponse:
    """Ingest an uploaded file into a session. If no session_id is given,
    a new session is created (Phase 4 adds POST /sessions for explicit
    creation) — so a first upload can bootstrap a session in one call."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported file type {suffix!r} (supported: {sorted(SUPPORTED_EXTENSIONS)})",
        )

    if session_id is None:
        session_id = (
            get_client().table("sessions").insert({}).execute().data[0]["id"]
        )

    # Loaders want a real file path; spool the upload to a temp file.
    # delete=False because Windows can't reopen an open NamedTemporaryFile.
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        result = ingest_file(tmp_path, file.filename or tmp_path.name, session_id)
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except EmptyDocument as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return UploadResponse(
        document_id=result.document_id,
        session_id=result.session_id,
        filename=file.filename or tmp_path.name,
        page_count=result.page_count,
        chunk_count=result.chunk_count,
    )
