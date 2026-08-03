# DESIGN.md

> This document records each non-obvious decision and its rationale. It
> grew with the project. It was not written after the fact.

## Chunking Strategy

The chunker uses recursive character splitting. It measures chunks in
tokens with tiktoken `cl100k_base`. The configuration is in
`app/config.py`:

- **600 tokens for each chunk.** This is the middle of the 500–800 band.
  A small chunk keeps the retrieved text relevant to the question. A
  large chunk keeps a procedure or an explanation in one piece. 600 is a
  balance of the two.
- **75-token overlap (12.5%).** A sentence that crosses a chunk boundary
  appears complete in at least one chunk. A boundary cannot hide an
  answer.
- **Why recursive splitting, not fixed-size splitting:** the recursive
  splitter prefers paragraph boundaries, then sentence boundaries, then
  word boundaries. Chunks align with the structure of the document. They
  do not cut through the middle of a thought.
- **Why tokens, not characters:** the 500–800 budget is a token budget.
  The splitter must count tokens the same way as the embedding model.
  Character counts drift ±30% with prose density.
- The splitter keeps page metadata. Answers can cite page numbers.

## Embedding Model

The embedder uses Gemini `gemini-embedding-001` and truncates the vectors
to 1536 dimensions. The configuration is in `app/config.py`. The project
started with OpenAI `text-embedding-3-small` and changed to Gemini during
the build. The Gemini free tier makes the demo reproducible at zero cost.

- The model is Matryoshka-trained. The API can truncate its native 3072
  dimensions at request time (`output_dimensionality=1536`) with small
  quality loss. The value 1536 matches the `vector(1536)` column. No
  migration was necessary.
- The API does not re-normalize truncated vectors. This is not a problem.
  The index uses cosine distance, and cosine distance is scale-invariant.
- Accepted tradeoff: free-tier rate limits cap the ingestion throughput.
  This is sufficient at demo scale. Production would use a paid tier or a
  self-hosted model.

## Index Choice (HNSW vs IVFFlat)

The index is HNSW with cosine distance (`vector_cosine_ops`). The reasons
to prefer it over IVFFlat:

- **Recall and latency.** HNSW gives better recall at low latency for
  small and medium collections. This project has a few thousand chunks
  for each session, well under 1M rows. HNSW is the correct tool at this
  scale.
- **No training step.** IVFFlat must build cluster lists from data that
  already exists. A fresh deployment has zero rows. HNSW does not have
  this problem. It builds incrementally on insert.
- **Cost.** HNSW uses more memory and builds more slowly. At this row
  count, the cost is negligible. At 10M+ vectors, this decision needs
  review. Options then: IVFFlat, or partitioning by tenant.
- **Cosine distance** is the safe default for text-embedding models.
  These models are trained for angular similarity. Cosine distance is
  also scale-invariant. This property later absorbed Gemini's
  un-renormalized truncated vectors at no cost.

## Session Isolation

The database enforces isolation, not the application code. The
`match_chunks` Postgres function (see `app/db/schema.sql`) receives a
`session_id` parameter. The function applies the filter inside its body,
before the vector ranking. API code never assembles its own similarity
SQL. Therefore no code path can return chunks from a different session. A
btree index on `chunks.session_id` keeps the filter fast. An automated
cross-contamination test verifies this behavior.

Two more layers:

- **Row Level Security (RLS) is on for all three tables, with no
  policies.** The public Supabase REST API (the publishable key) cannot
  read or write any table. Only the backend holds the secret key, and
  only the secret key bypasses RLS.
- **The browser stores nothing.** The session id is the access
  credential. The page keeps it in memory only. A shared computer cannot
  show one visitor the documents of a previous visitor. Accepted
  tradeoff: a page reload ends access to the session.

## LLM & Grounding

The LLM is `gemini-3-flash-preview` at temperature 0. The configuration
is in `app/config.py`. New Gemini API accounts have zero free-tier quota
on the older GA models. The pinned preview model is the only fixed free
option. A pinned model is necessary: the eval accuracy number is only
meaningful against a fixed model. The `gemini-flash-latest` alias can
change models silently.

The prompt enforces grounding (`app/retrieval/prompt.py`). The rules:

- Answer only from the numbered context excerpts.
- Cite the excerpts inline.
- If the excerpts do not contain the answer, return a fixed
  "couldn't find" sentence.

Manual verification: the out-of-scope question "What is the capital of
France?" returns the "couldn't find" sentence. It does not return world
knowledge.

## Eval Methodology

The eval set is 20 curated question-answer pairs (`eval/qa_set.json`).
The corpus is 3 real public documents, approximately 245 pages total (see
`eval/test_docs/SOURCE.md`). The harness is `eval/run_eval.py`. It
measures two separate metrics:

- **Retrieval accuracy** (the >90% target). Each pair contains an
  `expected_substring`. The check passes if the substring is in one of
  the k retrieved chunks. The comparison normalizes whitespace and case.
  This metric is objective and does not use an LLM. CI runs it as a
  regression gate on every push to main.
- **Answer accuracy** (the `--judge` flag). An LLM judge grades the final
  answer against a ground-truth answer, with a strict PASS/FAIL rubric.
  This metric is opt-in because of quota: the answer model's free tier is
  20 requests each day. That is exactly one eval run. The judge runs on a
  separate lite model, because daily quotas apply per model. The harness
  saves progress after each question. A quota failure mid-run does not
  lose completed work. A judge on a different model also reduces
  self-preference bias.

Each substring was validated against the ingested chunks before its pair
entered the set. A question that the corpus cannot answer measures
nothing. The eval session is ingested once and persists
(`eval/.session_id` or `EVAL_SESSION_ID`). Eval runs do not re-embed the
corpus. Ingestion variance cannot contaminate the results.

## Eval Iteration Log

| # | Date | Config (chunk/overlap/k) | Retrieval | Answer | Change and reasoning |
|---|---|---|---|---|---|
| 0 | 2026-08-03 | 600 / 75 / 4 | **95%** (19/20) | **95%** (19/20) | Baseline. No tuning was necessary. Both metrics are above target. |

The answer-accuracy failure is the same question as the retrieval failure
(Q15). Retrieval did not surface the `--fixtures` chunk. The grounded
prompt correctly answered "not found". The judge failed that answer. This
is the desired failure mode: **when retrieval misses, the system says so.
It does not hallucinate.** Retrieval quality is the accuracy ceiling.
Generation is faithful to it.

**Failure analysis (Q15, "list available fixtures"):** the `--fixtures`
chunk does not appear in the top 10 results. Two root causes are visible
in the top 10: (1) table-of-contents chunks pollute the ranking — their
dot-leader lines overlap lexically with everything; (2) the pytest and
mypy PDFs extract with glued words ("Howtoinvokepytest"), which degrades
the embedding quality of those chunks. Candidate fixes, if the target
were at risk: filter TOC-like chunks at ingestion, or use HTML or text
sources instead of PDF. **The decision was to not tune.** The baseline is
above the 90% target. Tuning for one eval question risks overfitting the
eval set.

**A note on eval integrity:** the first corpus draft included documents
from `click.readthedocs.io`. That site hosts Ubuntu's "Click Packages"
project, not the Python click library. The substring validation caught
this error before the eval ran. Validation is what makes the accuracy
number mean something.

## Performance

Measurements from 2026-08-03: 30 sequential searches, then 30 searches
with 8 parallel workers, against the 362-chunk eval corpus, from a local
machine to Gemini and Supabase.

| Component | p50 | p95 | max |
|---|---|---|---|
| Query embedding (Gemini) | 316 ms | 392 ms | 445 ms |
| pgvector `match_chunks` | 180 ms | 535 ms | 930 ms |
| **Search end-to-end** | **492 ms** | **917 ms** | 1375 ms |
| Search with 8 parallel workers | 710 ms | 912 ms | 914 ms |

**The sub-second p95 target is met.** The index was deliberately not
tuned. HNSW over a few hundred vectors completes in microseconds. The p95
is network round-trip time: the embedding API plus the Supabase REST
call. To tune `ef_search` would adjust a microsecond term in a
millisecond problem. Review this decision only above 100,000 vectors per
session.

## Known Limitations / What I Would Do Differently at Scale

- **Blocking ingestion.** `/documents/upload` holds the HTTP request open
  during embedding. Large documents take minutes on free-tier rate
  limits. The production answer: return 202 with a job id, ingest in a
  background worker, and expose a status endpoint. Serverless execution
  time limits also require this change.
- **In-memory rate limiter.** The limiter lives in one process. Each warm
  serverless instance has its own limit. The limit is therefore soft
  under horizontal scale. The production answer: a shared store, such as
  Redis or a Postgres counter.
- **Free-tier LLM daily quota** (about 20 requests each day per model)
  caps the question volume of the live demo. A paid tier or a self-hosted
  model removes the cap.
- **PDF text extraction quality.** Glued words and table-of-contents
  noise degrade retrieval. The one eval failure traces to this. The
  production answer: prefer HTML or markdown sources, clean the text, and
  filter boilerplate chunks at ingestion.
- **No authentication.** A session id is an unguessable UUID, a
  capability URL. This is acceptable for a demo. A real deployment needs
  user authentication tied to sessions.
