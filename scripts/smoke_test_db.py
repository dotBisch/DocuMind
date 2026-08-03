"""Phase 2 smoke test: insert a dummy vector chunk and retrieve it via
similarity search. Run once after applying schema.sql to a fresh
Supabase project, from the repo root (as a module, so `app` imports
resolve):

    python -m scripts.smoke_test_db

Cleans up after itself (deleting the session cascades to the chunk).
"""

import random

from app.db.client import get_client

EMBEDDING_DIM = 1536


def main() -> None:
    client = get_client()

    session = client.table("sessions").insert({}).execute().data[0]
    session_id = session["id"]
    print(f"created session {session_id}")

    document = (
        client.table("documents")
        .insert({"session_id": session_id, "filename": "smoke_test.txt"})
        .execute()
        .data[0]
    )
    print(f"created document {document['id']}")

    embedding = [random.uniform(-1, 1) for _ in range(EMBEDDING_DIM)]
    client.table("chunks").insert(
        {
            "document_id": document["id"],
            "session_id": session_id,
            "content": "smoke test chunk",
            "embedding": embedding,
        }
    ).execute()
    print("inserted chunk with dummy embedding")

    matches = client.rpc(
        "match_chunks",
        {
            "query_embedding": embedding,
            "match_session_id": session_id,
            "match_count": 1,
        },
    ).execute()

    assert matches.data, "similarity search returned no rows"
    top = matches.data[0]
    assert top["content"] == "smoke test chunk"
    # Querying with the exact same vector should give similarity ~1.0.
    assert top["similarity"] > 0.99, f"unexpected similarity {top['similarity']}"
    print(f"similarity search OK (similarity={top['similarity']:.4f})")

    client.table("sessions").delete().eq("id", session_id).execute()
    print("cleaned up — smoke test PASSED")


if __name__ == "__main__":
    main()
