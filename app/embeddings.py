"""Embedding generation — shared by BOTH pipelines (ingestion embeds
chunks, retrieval embeds queries). It lives outside ingestion/ and
retrieval/ deliberately: query and chunk vectors must come from the same
model/dimension or similarity search silently degrades, so the embedder
is the shared contract between the two, not part of either.

The model is set in app.config (never here) so swapping providers is a
config change plus a schema migration."""

import logging
import time
from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai._common import GoogleGenerativeAIError

from app.config import EMBEDDING_DIM, EMBEDDING_MODEL, GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Gemini free tier caps tokens-per-minute; 30 chunks x ~600 tokens keeps
# each request well under it. Not a retrieval-quality knob -> not config.py.
_BATCH_SIZE = 30
_MAX_RETRIES = 6
_RETRY_WAIT_SECONDS = 30  # quota window is per-minute; half-window retries


@lru_cache(maxsize=1)
def _embeddings() -> GoogleGenerativeAIEmbeddings:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY must be set (see .env.example)")
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL, google_api_key=GEMINI_API_KEY
    )


def _embed_batch_with_retry(batch: list[str]) -> list[list[float]]:
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            # output_dimensionality truncates Gemini's native 3072 dims to
            # the DB column size; cosine distance is scale-invariant, so
            # un-renormalized truncated vectors are fine with our index.
            return _embeddings().embed_documents(
                batch, output_dimensionality=EMBEDDING_DIM
            )
        except GoogleGenerativeAIError as exc:
            rate_limited = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            if not rate_limited or attempt == _MAX_RETRIES:
                raise
            logger.warning(
                "embedding rate-limited (attempt %d/%d), waiting %ds",
                attempt,
                _MAX_RETRIES,
                _RETRY_WAIT_SECONDS,
            )
            time.sleep(_RETRY_WAIT_SECONDS)
    raise AssertionError("unreachable")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed chunk texts in rate-limit-friendly batches with backoff."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        vectors.extend(_embed_batch_with_retry(texts[start : start + _BATCH_SIZE]))
    return vectors
