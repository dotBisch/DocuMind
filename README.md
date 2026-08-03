# DocuMind

**Ask questions against your documents — answers grounded in their content, with cited sources.**

DocuMind is a retrieval-augmented generation (RAG) tool framed as an internal
knowledge-base assistant: upload runbooks, handbooks, or technical docs into a
session, then ask questions answered *only* from that session's content. When
the answer isn't in the documents, it says so instead of guessing.

**Live demo:** https://documind-henna-nu.vercel.app
*(runs on free-tier LLM quota — if you get a "quota exhausted" message, try again later)*

## Results (measured, not aspirational)

| Metric | Result | Method |
|---|---|---|
| Retrieval accuracy | **95%** (19/20) | expected content present in top-k retrieved chunks, objective substring check — `eval/run_eval.py` |
| Answer accuracy | **95%** (19/20) | LLM-as-judge (separate model) vs ground-truth answers — `eval/run_eval.py --judge` |
| Semantic search p95 | **917ms** sequential, **912ms** under 8-way concurrency | 60 timed searches over a 362-chunk corpus — `scripts/measure_latency.py` |

The single failure in both metrics is the *same* question: retrieval missed
the relevant chunk, the grounded prompt answered "not found", and the judge
failed it — i.e. when retrieval misses, the system admits it rather than
hallucinating. Full methodology, iteration log, and failure analysis in
[DESIGN.md](DESIGN.md).

## How it works

```
 upload                                  question
   │                                        │
   ▼                                        ▼
 loader ─► chunker ─► embedder ─► pgvector  │
 (PDF/txt,  (600-token  (Gemini,   (Supabase,│
  per page)  chunks,     1536-dim)  HNSW +   │
             12.5%                  session  │
             overlap)               filter)◄─┴─ embed query
                                       │
                                       ▼
                          top-k chunks ─► grounded prompt ─► LLM ─► answer + cited sources
```

- **Session isolation is enforced in the database**: similarity search runs
  through a SQL function that takes `session_id` as a parameter and filters
  inside — no API code path can return another session's chunks. RLS is
  enabled on all tables as defense in depth.
- **Ingestion and retrieval are decoupled pipelines** sharing one contract:
  the embedder (`app/embeddings.py`) — queries and chunks must live in the
  same vector space.
- **The eval set is the core artifact**: 20 Q&A pairs against real public
  docs, every pair validated to be answerable from the ingested corpus, run
  in CI as a regression gate.

**Stack:** FastAPI · LangChain · Supabase Postgres + pgvector (HNSW, cosine) ·
Gemini (embeddings + LLM) · Vercel

## Quickstart

Prereqs: Python 3.12, a [Supabase](https://supabase.com) project, a
[Gemini API key](https://aistudio.google.com) (free tier works).

```bash
git clone https://github.com/dotBisch/DocuMind.git && cd DocuMind
python -m venv .venv && .venv/Scripts/activate   # Windows; use bin/activate on unix
pip install -r requirements.txt

# 1. database: paste app/db/schema.sql into the Supabase SQL editor and run it
# 2. credentials
cp .env.example .env    # fill in SUPABASE_URL, SUPABASE_KEY (secret key), GEMINI_API_KEY
# 3. sanity check the database wiring
python -m scripts.smoke_test_db
# 4. run
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 — upload a PDF, ask a question.

```bash
pytest                                # unit + integration tests (live tests skip without credentials)
python -m eval.run_eval --ingest      # one-time: build the eval corpus session
python -m eval.run_eval               # retrieval accuracy
python -m eval.run_eval --judge       # + LLM-judged answer accuracy
python -m scripts.measure_latency     # p50/p95 search latency
```

## Why these documents?

The eval corpus (`eval/test_docs/`) is real public technical documentation —
the requests, pytest, and mypy docs — because that's exactly the genre of
material an internal engineering knowledge base holds: library guides,
how-tos, reference pages. Real docs make the demo credible and the eval
reproducible by anyone; sources and licenses in
[eval/test_docs/SOURCE.md](eval/test_docs/SOURCE.md).

## Repo tour

| Path | What |
|---|---|
| `app/ingestion/` | upload → load → chunk → embed → store pipeline |
| `app/retrieval/` | session-scoped search → grounded prompt → answer |
| `app/embeddings.py` | the shared embedder (the contract between the two pipelines) |
| `app/db/schema.sql` | single source of truth: tables, HNSW index, `match_chunks` |
| `eval/` | the 20-pair eval set, harness, and test corpus |
| `DESIGN.md` | every non-obvious decision + the eval iteration log |
