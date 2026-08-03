# DESIGN.md

> Filled in progressively as decisions are made — not written retroactively.

## Chunking Strategy

_TBD — Phase 3/5_

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
