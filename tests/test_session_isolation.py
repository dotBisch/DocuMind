"""Integration test: two sessions with different documents must never
see each other's chunks in retrieval results.

Runs against live Supabase + Gemini, so it's skipped when credentials
aren't configured (e.g. in CI without secrets). Locally: pytest runs it
— CLAUDE.md requires it for any retrieval change.
"""

import tempfile
from pathlib import Path

import pytest

from app.config import GEMINI_API_KEY, SUPABASE_KEY, SUPABASE_URL

pytestmark = pytest.mark.skipif(
    not (SUPABASE_URL and SUPABASE_KEY and GEMINI_API_KEY),
    reason="live-service credentials not configured",
)

SECRET_A = "The staging deploy password is falcon-blue-7."
SECRET_B = "The guest wifi password is tangerine-sky-9."


@pytest.fixture()
def two_sessions():
    from app.db.client import get_client
    from app.ingestion.pipeline import ingest_file

    client = get_client()
    session_ids = []
    try:
        for secret in (SECRET_A, SECRET_B):
            session_id = client.table("sessions").insert({}).execute().data[0]["id"]
            session_ids.append(session_id)
            with tempfile.NamedTemporaryFile(
                "w", suffix=".txt", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(secret)
                path = Path(tmp.name)
            ingest_file(path, "secret.txt", session_id)
            path.unlink(missing_ok=True)
        yield session_ids
    finally:
        # cascade delete cleans up documents and chunks too
        for session_id in session_ids:
            client.table("sessions").delete().eq("id", session_id).execute()


def test_no_cross_session_leakage(two_sessions):
    from app.retrieval.search import search_chunks

    session_a, session_b = two_sessions

    results_a = search_chunks(session_a, "what is the staging deploy password?")
    results_b = search_chunks(session_b, "what is the staging deploy password?")

    # each session sees its own single chunk and nothing else
    assert [c.content for c in results_a] == [SECRET_A]
    assert [c.content for c in results_b] == [SECRET_B]


def test_empty_session_retrieves_nothing(two_sessions):
    from app.db.client import get_client
    from app.retrieval.search import search_chunks

    client = get_client()
    empty_session = client.table("sessions").insert({}).execute().data[0]["id"]
    try:
        assert search_chunks(empty_session, "anything at all?") == []
    finally:
        client.table("sessions").delete().eq("id", empty_session).execute()
