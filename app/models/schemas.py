"""Pydantic request/response models."""

from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: str
    session_id: str
    filename: str
    page_count: int
    chunk_count: int
