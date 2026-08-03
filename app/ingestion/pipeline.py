"""Ingestion pipeline: load -> chunk -> embed -> store.

Orchestration lives here (not in the API layer) so it can be tested and
tuned without HTTP, and so retrieval code never imports from it.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from app.db.client import get_client
from app.embeddings import embed_texts
from app.ingestion.chunker import chunk_documents
from app.ingestion.loader import load_document

logger = logging.getLogger(__name__)

# Rows per insert request — keeps payload sizes well under PostgREST
# limits; not a retrieval-quality knob, so it doesn't live in config.py.
_INSERT_BATCH_SIZE = 200


class EmptyDocument(ValueError):
    """The file contained no extractable text."""


@dataclass
class IngestResult:
    document_id: str
    session_id: str
    page_count: int
    chunk_count: int


def ingest_file(path: Path, filename: str, session_id: str) -> IngestResult:
    pages = load_document(path)
    if not pages:
        raise EmptyDocument(f"{filename} contained no extractable text")

    chunks = chunk_documents(pages)
    embeddings = embed_texts([c.page_content for c in chunks])

    client = get_client()
    document = (
        client.table("documents")
        .insert(
            {
                "session_id": session_id,
                "filename": filename,
                "page_count": len(pages),
            }
        )
        .execute()
        .data[0]
    )

    rows = [
        {
            "document_id": document["id"],
            "session_id": session_id,
            "content": chunk.page_content,
            "embedding": embedding,
            # page number (0-based from the loader) kept for source citation
            "metadata": {"page": chunk.metadata.get("page")},
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]
    for start in range(0, len(rows), _INSERT_BATCH_SIZE):
        client.table("chunks").insert(rows[start : start + _INSERT_BATCH_SIZE]).execute()

    logger.info(
        "ingested %s: %d pages -> %d chunks (document %s, session %s)",
        filename,
        len(pages),
        len(chunks),
        document["id"],
        session_id,
    )
    return IngestResult(
        document_id=document["id"],
        session_id=session_id,
        page_count=len(pages),
        chunk_count=len(chunks),
    )
