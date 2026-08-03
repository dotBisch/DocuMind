# DESIGN.md

> Filled in progressively as decisions are made — not written retroactively.

## Chunking Strategy

**Recursive character splitting, measured in tokens** (tiktoken
`cl100k_base` — the same encoding the embedding model uses), configured in
`app/config.py`:

- **600 tokens per chunk** — mid-range of the 500–800 band. Small enough
  that a retrieved chunk is mostly signal for the question that matched
  it; large enough that a procedure or explanation usually survives in
  one piece. Starting point, not gospel — Phase 5 tunes this against the
  eval set and logs each iteration below.
- **75-token overlap (12.5%)** — a sentence that straddles a chunk
  boundary appears whole in at least one chunk, so boundary placement
  can't hide an answer.
- **Why recursive splitting** (vs fixed-size): it prefers paragraph, then
  sentence, then word boundaries, so chunks tend to align with the
  document's own structure instead of cutting mid-thought.
- **Why token-measured** (vs characters): the 500–800 budget is only
  enforceable if we count tokens the way the embedding model does;
  character counts drift ±30% depending on prose density.
- Page metadata is preserved through splitting so answers can cite
  page numbers.

## Embedding Model

**Gemini `gemini-embedding-001`, truncated to 1536 dims** (config:
`app/config.py`). Chosen over OpenAI `text-embedding-3-small` mid-build:
the free tier makes the demo reproducible at zero cost, which fits the
portfolio goal. Notes:

- The model is Matryoshka-trained: its native 3072 dims can be truncated
  at request time (`output_dimensionality=1536`) with minimal quality
  loss, and 1536 matches the existing `vector(1536)` column — no
  migration needed.
- Truncated vectors aren't re-normalized, but our index uses **cosine**
  distance, which is scale-invariant — so no renormalization step.
- Tradeoff accepted: free-tier rate limits (requests/tokens per minute)
  cap ingestion throughput; fine at demo scale, would swap to a paid
  tier or self-hosted model in production.

## Index Choice (HNSW vs IVFFlat)

Chose **HNSW with cosine distance** (`vector_cosine_ops`) over IVFFlat:

- **Recall/latency tradeoff:** HNSW gives better recall at low latency for
  small-to-mid collections. Our scale (a few thousand chunks per session,
  well under 1M rows total) is squarely where HNSW wins.
- **No training step:** IVFFlat requires building cluster lists from data
  that already exists — on a fresh deploy with zero rows, that's a chicken-
  and-egg problem. HNSW builds incrementally as rows are inserted.
- **Cost:** HNSW uses more memory and builds slower, but at our row counts
  that's negligible. At 10M+ vectors this decision would need revisiting
  (IVFFlat or partitioning by tenant).
- **Cosine distance** matches how OpenAI-style embedding models are trained;
  their vectors are normalized, so cosine and inner product are equivalent,
  and cosine is the conventional/safer default.

## Session Isolation Approach

Isolation is enforced **at the query layer, not in application code**: the
`match_chunks` Postgres function (see `app/db/schema.sql`) takes a
`session_id` parameter and applies the filter inside the function body
before the vector ordering. API code never assembles its own similarity
SQL, so there is no code path that can return cross-session chunks.
A btree index on `chunks.session_id` keeps that filter cheap.
(Verified by an explicit cross-contamination test in Phase 4.)

Defense in depth: **RLS is enabled on all three tables with no policies
defined**, so Supabase's auto-generated public REST API (anon key) can't
read or write anything. Only the backend, holding the service_role key
server-side, can touch the data.

## Session Isolation Approach

_TBD — Phase 4_

## Eval Iteration Log

_TBD — Phase 5_

## Known Limitations / What I'd Do Differently at Scale

_TBD — Phase 7_
