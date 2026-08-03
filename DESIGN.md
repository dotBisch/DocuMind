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

## LLM & Grounding

`gemini-3-flash-preview`, temperature 0 (config: `app/config.py`). New
Gemini API accounts have zero free-tier quota on the older GA models, so
the pinned preview is the only fixed free option — pinned over the
`gemini-flash-latest` alias because the eval accuracy number is only
meaningful against a fixed model.

Grounding is enforced in the prompt (`app/retrieval/prompt.py`): answer
only from numbered excerpts, cite inline, and return a fixed
"couldn't find" string when the context lacks the answer. Verified
manually: an out-of-scope question ("capital of France?") returns the
not-found string rather than world knowledge.

## Eval Methodology

20 curated Q&A pairs (`eval/qa_set.json`) against 3 real public docs
(~245 pages total — see `eval/test_docs/SOURCE.md`), run by
`eval/run_eval.py`. Two separate metrics:

- **Retrieval accuracy** (the >90% target): each pair carries an
  `expected_substring` that must appear in one of the k retrieved
  chunks (whitespace/case-normalized). Objective — no judge, no LLM
  cost — so it runs in CI as a regression gate on every push to main.
- **Answer accuracy** (`--judge` flag): LLM-as-judge grades the final
  answer against a ground-truth answer, strict PASS/FAIL. Opt-in rather
  than CI-default because of quota: the answer model's free tier is
  **20 requests/day** — exactly one eval's worth. The judge therefore
  runs on a separate lite model (daily quotas are per-model, so it gets
  its own 20/day), and per-question progress is persisted so a mid-run
  quota failure resumes instead of restarting. Judging on a different
  model than the one being graded also mildly reduces self-preference
  bias.

Every substring was validated to exist in the ingested chunks before
the pair entered the set — a question whose answer isn't in the corpus
measures nothing. The eval session is ingested once and persisted
(`eval/.session_id` / `EVAL_SESSION_ID`), so eval runs don't re-embed
the corpus and results aren't confounded by ingestion variance.

## Eval Iteration Log

| # | Date | Config (chunk/overlap/k) | Retrieval | Answer | Change & reasoning |
|---|---|---|---|---|---|
| 0 | 2026-08-03 | 600 / 75 / 4 | **95%** (19/20) | _pending_ | Baseline — no tuning yet. |

**Baseline failure analysis (Q15, "list available fixtures"):** the
`--fixtures` chunk doesn't appear even at k=10. Two root causes, both
visible in the top-10: (1) table-of-contents chunks — dot-leader lines
with high lexical overlap with everything — pollute the ranking; (2) the
pytest/mypy PDFs extract with glued words ("Howtoinvokepytest"), which
degrades embedding quality for those chunks. Candidate fixes if the
target were at risk: filter low-alpha/TOC-like chunks at ingestion, or
switch corpus format from PDF to HTML/text. **Deliberately not tuned:**
baseline already exceeds the 90% target, and optimizing for one eval
question invites overfitting the eval set (and gold-plating past the
project's stated scope).

**A note on eval integrity:** the first corpus draft included
`click.readthedocs.io` docs that turned out to be Ubuntu's "Click
Packages" project, not the Python click library — caught because every
`expected_substring` is validated against the ingested chunks before a
pair enters the set. A Q&A pair whose answer isn't in the corpus
measures nothing; validation is what makes the accuracy number mean
something.

## Performance

Measured 2026-08-03 (30 sequential + 30 concurrent×8 searches against
the 362-chunk eval corpus, local machine → Gemini + Supabase):

| Component | p50 | p95 | max |
|---|---|---|---|
| Query embedding (Gemini) | 316ms | 392ms | 445ms |
| pgvector `match_chunks` | 180ms | 535ms | 930ms |
| **Search end-to-end** | **492ms** | **917ms** | 1375ms |
| Search under concurrency (8 workers) | 710ms | 912ms | 914ms |

**Sub-second p95 target: met.** Deliberately *not* tuned: HNSW over a
few hundred vectors does its work in microseconds — the p95 is entirely
network RTT (embedding API + Supabase REST). Tuning `ef_search` would
turn a microsecond knob on a millisecond problem; revisit only at
5–6 figures of vectors per session.

## Known Limitations / What I'd Do Differently at Scale

- **Blocking ingestion:** `/documents/upload` holds the HTTP request
  open while embedding (minutes for big docs on free-tier rate limits).
  Production answer: return 202 + job id, ingest in a background
  worker, expose status. Also required by serverless execution caps.
- **In-memory rate limiter:** per warm serverless instance, so the
  limit is soft under horizontal scale. Production answer: shared
  store (Redis or a Postgres counter).
- **Free-tier LLM daily quota (~20 requests/day/model)** caps the live
  demo's question volume; paid tier or self-hosted model removes it.
- **PDF text extraction quality** (glued words, TOC noise in some
  PDFs) measurably degrades retrieval — the one eval failure traces to
  it. Production answer: prefer HTML/markdown sources, add a text
  cleanup pass, and filter boilerplate chunks at ingestion.
- **No auth:** sessions are unguessable UUIDs (capability URLs), fine
  for a demo; real deployment needs user auth tied to sessions.
