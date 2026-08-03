from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.api.query import router as query_router
from app.api.sessions import router as sessions_router

app = FastAPI(title="DocuMind")
app.include_router(documents_router)
app.include_router(sessions_router)
app.include_router(query_router)


@app.get("/health")
def health():
    return {"status": "ok"}
