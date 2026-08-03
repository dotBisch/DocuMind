# DocuMind

DocuMind is a question-and-answer tool for documents. It uses
retrieval-augmented generation (RAG).

You upload documents into a session. Then you ask questions about them.
DocuMind makes each answer only from the content of your documents. Each
answer shows its source passages. If your documents do not contain the
answer, DocuMind tells you. It does not guess.

**Live demo:** https://documind-henna-nu.vercel.app
The demo uses a free LLM quota. If you see a "quota exhausted" message,
try again later.

## Results

The table below shows measured results. The repository contains the script
that made each measurement.

| Metric | Result | Method |
|---|---|---|
| Retrieval accuracy | **95%** (19/20) | `eval/run_eval.py` checks that the expected content is in the top-k retrieved chunks. This check is an objective substring match. |
| Answer accuracy | **95%** (19/20) | `eval/run_eval.py --judge` uses a second LLM to grade each answer against a ground-truth answer. |
| Search latency, p95 | **917 ms** sequential, **912 ms** with 8 parallel clients | `scripts/measure_latency.py` times 60 searches on a 362-chunk corpus. |

The two failed checks are the same question. Retrieval did not find the
correct chunk. The system then answered "not found". It did not invent an
answer. See [DESIGN.md](DESIGN.md) for the full analysis.

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

- The database enforces session isolation. The similarity search runs in a
  SQL function. The function filters by `session_id` before it ranks
  chunks. No API code path can return chunks from a different session.
  Row Level Security (RLS) is on for all tables as a second layer.
- Ingestion and retrieval are two separate pipelines. They share one
  module: the embedder (`app/embeddings.py`). Query vectors and chunk
  vectors must come from the same model.
- The eval set is the core artifact of this project. It contains 20
  question-answer pairs against real public documents. Each pair is
  validated against the ingested corpus. CI runs the eval as a regression
  gate.

**Stack:** FastAPI · LangChain · Supabase Postgres + pgvector (HNSW,
cosine) · Gemini (embeddings + LLM) · Vercel

## Quickstart

Before you start, you need:

- Python 3.12
- A [Supabase](https://supabase.com) project
- A [Gemini API key](https://aistudio.google.com) (the free tier is
  sufficient)

Do these steps:

1. Clone the repository and install the dependencies:
   ```bash
   git clone https://github.com/dotBisch/DocuMind.git && cd DocuMind
   python -m venv .venv && .venv/Scripts/activate   # on unix: source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Open the Supabase SQL editor. Paste the content of
   `app/db/schema.sql`. Run it.
3. Copy `.env.example` to `.env`. Fill in `SUPABASE_URL`, `SUPABASE_KEY`
   (the secret key), and `GEMINI_API_KEY`.
4. Test the database connection:
   ```bash
   python -m scripts.smoke_test_db
   ```
5. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```
6. Open http://127.0.0.1:8000 in a browser. Start a session. Upload a
   document. Ask a question.

To run the tests and the measurements:

```bash
pytest                                # tests that need credentials skip without them
python -m eval.run_eval --ingest      # do this once: build the eval corpus session
python -m eval.run_eval               # measure retrieval accuracy
python -m eval.run_eval --judge       # also measure answer accuracy
python -m scripts.measure_latency     # measure search latency
```

## Why these documents?

The eval corpus (`eval/test_docs/`) contains real public technical
documentation: the requests, pytest, and mypy docs. An internal knowledge
base holds the same type of material: library guides, how-to documents,
and reference pages. Real documents make the demo credible. They also make
the eval reproducible by anyone. See
[eval/test_docs/SOURCE.md](eval/test_docs/SOURCE.md) for sources and
licenses.

## Repository tour

| Path | Content |
|---|---|
| `app/ingestion/` | The upload pipeline: load, chunk, embed, store |
| `app/retrieval/` | Session-scoped search, grounded prompt, answer |
| `app/embeddings.py` | The shared embedder for both pipelines |
| `app/db/schema.sql` | The single source of truth: tables, HNSW index, `match_chunks` |
| `eval/` | The 20-pair eval set, the harness, and the test corpus |
| `DESIGN.md` | Each non-obvious decision, with its rationale and the eval iteration log |
