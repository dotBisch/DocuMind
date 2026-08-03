"""Pydantic request/response models."""

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    document_id: str
    session_id: str
    filename: str
    page_count: int
    chunk_count: int


class SessionResponse(BaseModel):
    session_id: str


class QueryRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1, max_length=2000)


class Source(BaseModel):
    document_id: str
    page: int | None = None
    similarity: float
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
