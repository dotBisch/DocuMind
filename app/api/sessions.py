"""POST /sessions — HTTP concerns only."""

from fastapi import APIRouter

from app.db.client import get_client
from app.models.schemas import SessionResponse

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session() -> SessionResponse:
    row = get_client().table("sessions").insert({}).execute().data[0]
    return SessionResponse(session_id=row["id"])
