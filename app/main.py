import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import middleware
from app.api.documents import router as documents_router
from app.api.query import router as query_router
from app.api.sessions import router as sessions_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="DocuMind")
middleware.install(app)
app.include_router(documents_router)
app.include_router(sessions_router)
app.include_router(query_router)

_INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(_INDEX)


@app.get("/health")
def health():
    return {"status": "ok"}
