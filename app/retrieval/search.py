"""Similarity search against pgvector, always session-scoped.

The session filter lives inside the match_chunks SQL function
(app/db/schema.sql), so there is no code path here — or anywhere —
that can return another session's chunks.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.config import RETRIEVAL_K
from app.db.client import get_client
from app.embeddings import embed_texts

logger = logging.getLogger("documind.retrieval")


@dataclass
class RetrievedChunk:
    id: str
    document_id: str
    content: str
    metadata: dict[str, Any]
    similarity: float


def search_chunks(session_id: str, question: str, k: int = RETRIEVAL_K) -> list[RetrievedChunk]:
    """Embed the question and return the k most similar chunks in this
    session. Uses the same embedder as ingestion so query and chunk
    vectors share one embedding space."""
    start = time.perf_counter()
    [query_embedding] = embed_texts([question])
    embed_ms = round((time.perf_counter() - start) * 1000)

    start = time.perf_counter()
    rows = (
        get_client()
        .rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "match_session_id": session_id,
                "match_count": k,
            },
        )
        .execute()
        .data
    )
    search_ms = round((time.perf_counter() - start) * 1000)

    # question text deliberately not logged (may contain sensitive content)
    logger.info(
        "search: session=%s k=%d embed_ms=%d search_ms=%d top_similarity=%s",
        session_id,
        k,
        embed_ms,
        search_ms,
        round(rows[0]["similarity"], 4) if rows else None,
    )
    return [
        RetrievedChunk(
            id=row["id"],
            document_id=row["document_id"],
            content=row["content"],
            metadata=row["metadata"] or {},
            similarity=row["similarity"],
        )
        for row in rows
    ]
