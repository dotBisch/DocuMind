"""Similarity search against pgvector, always session-scoped.

The session filter lives inside the match_chunks SQL function
(app/db/schema.sql), so there is no code path here — or anywhere —
that can return another session's chunks.
"""

from dataclasses import dataclass
from typing import Any

from app.config import RETRIEVAL_K
from app.db.client import get_client
from app.embeddings import embed_texts


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
    [query_embedding] = embed_texts([question])
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
