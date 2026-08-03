"""POST /query — HTTP concerns only; retrieval/qa.py does the work."""

from fastapi import APIRouter, HTTPException

from app.db.client import get_client
from app.models.schemas import QueryRequest, QueryResponse, Source
from app.retrieval.qa import answer_question

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    session_exists = (
        get_client()
        .table("sessions")
        .select("id")
        .eq("id", request.session_id)
        .execute()
        .data
    )
    if not session_exists:
        raise HTTPException(status_code=404, detail="session not found")

    result = answer_question(request.session_id, request.question)
    return QueryResponse(
        answer=result.answer,
        sources=[
            Source(
                document_id=chunk.document_id,
                page=chunk.metadata.get("page"),
                similarity=round(chunk.similarity, 4),
                excerpt=chunk.content[:200],
            )
            for chunk in result.sources
        ],
    )
