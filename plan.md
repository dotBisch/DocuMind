# DocuMind — Build Plan for Claude Code

> **How to use this file:** Work top to bottom, one phase at a time. Do not skip
> ahead to a later phase until every task in the current phase is checked off and
> the "Definition of Done" for that phase is met. After finishing a phase, stop
> and summarize what changed before starting the next one. If a decision below
> conflicts with something more efficient, flag it instead of silently changing it.
> Read `CLAUDE.md` first — it has persistent conventions that apply to every phase
> below and isn't repeated here.

---

## 0. Project Overview

**What we're building:** DocuMind — a document Q&A tool framed as an **internal
knowledge base assistant**: the kind of tool employees would use to ask questions
against internal docs (runbooks, handbooks, technical documentation) instead of
manually searching a wiki. Users upload one or more documents (up to 100 pages
each) into a session, and ask questions answered only from that session's
content, using retrieval-augmented generation (RAG).

**This is a portfolio project.** The deliverable isn't just working code — it's
a repo and live demo that clearly shows real RAG engineering judgment to a
technical interviewer. That means documented tradeoffs and a rigorous eval
methodology matter as much as the code itself. See `CLAUDE.md` for how this
affects day-to-day decisions.

**Stack:**
- Backend: Python, FastAPI
- Orchestration: LangChain
- Vector store: Supabase Postgres + pgvector
- Deployment: Vercel (API) + Supabase (DB)

**Success criteria (do not consider the project "done" until these are met):**
- Semantic search returns results in **sub-second** p95 latency
- Retrieval accuracy **>90%** on the 20-pair curated eval set (`/eval/qa_set.json`)
- Supports **multi-document sessions** (isolated per session, no cross-contamination)
- Handles documents up to **100 pages**
- `DESIGN.md` explains the *why* behind key decisions (chunking, indexing, isolation)
- `README.md` links a live Vercel demo and states measured (not aspirational) accuracy/latency

---

## Phase 1 — Project Scaffolding

**Goal:** A deployable skeleton exists before any real logic is written.

- [ ] Initialize git repo, create `.gitignore` (Python, env files, `__pycache__`, `.vercel`)
- [ ] Confirm `CLAUDE.md` is present at repo root (persistent context, read every session)
- [ ] Create folder structure exactly as defined in Section 1 below
- [ ] Create empty `DESIGN.md` and `README.md` stubs with headers only —
      filled in progressively as decisions are made (not written retroactively
      at the end)
- [ ] Set up `pyproject.toml` or `requirements.txt` with pinned versions:
      `fastapi`, `uvicorn`, `langchain`, `langchain-community`, `supabase`,
      `pgvector`, `python-dotenv`, `pytest`
- [ ] Create `.env.example` with placeholders: `SUPABASE_URL`, `SUPABASE_KEY`,
      `OPENAI_API_KEY` (or chosen embedding provider), `DATABASE_URL`
- [ ] Create a minimal FastAPI app with a `GET /health` endpoint returning `{"status": "ok"}`
- [ ] Confirm the app runs locally with `uvicorn app.main:app --reload`
- [ ] Set up `vercel.json` and deploy the skeleton to Vercel — confirm `/health`
      responds in production before writing any other code
- [ ] Set up GitHub Actions CI: run `pytest` and a linter (`ruff` or `flake8`) on every PR

**Definition of Done:** Empty app deploys successfully to Vercel and CI passes on a trivial PR.

---

## Phase 2 — Database & Schema

**Goal:** Supabase is provisioned and can store documents, chunks, and sessions.

- [ ] Create Supabase project, enable the `pgvector` extension
- [ ] Create schema (see Section 2 for full SQL) with tables: `sessions`,
      `documents`, `chunks`
- [ ] Create an HNSW index on the `chunks.embedding` column
- [ ] Write a `db/client.py` module wrapping the Supabase client — no raw
      connection strings scattered across the codebase
- [ ] Write a smoke-test script that inserts and queries a dummy vector row

**Definition of Done:** A test script can insert a fake chunk with an embedding
and retrieve it via similarity search from Supabase.

---

## Phase 3 — Ingestion Pipeline

**Goal:** A document can be uploaded, chunked, embedded, and stored.

- [ ] Implement `POST /documents/upload` (accepts PDF/text, returns `document_id`)
- [ ] Implement document loader using LangChain (`PyPDFLoader` or equivalent)
- [ ] Implement chunking: recursive character/text splitter, **chunk size 500–800
      tokens, 10–15% overlap** (confirm this against eval results in Phase 5 —
      don't treat as final)
- [ ] Implement embedding generation and batch write to `chunks` table, tagged
      with `session_id` and `document_id`
- [ ] Handle edge cases: empty pages, very short documents, non-text content
      (skip gracefully, log a warning, don't crash the pipeline)
- [ ] Write unit tests for chunking logic (short doc, 100-page doc, malformed input)

**Definition of Done:** Uploading a real 100-page PDF completes without error and
produces the expected number of chunk rows in Supabase.

---

## Phase 4 — Retrieval & Q&A Pipeline

**Goal:** A question returns a grounded answer using only session-scoped context.

- [ ] Implement `POST /sessions` (creates a session, returns `session_id`)
- [ ] Implement `POST /query` — accepts `session_id` + question, returns answer + sources
- [ ] Retrieval step: embed the query, similarity search **filtered by `session_id`**
      (this is the multi-doc isolation guarantee — test it explicitly)
- [ ] Assemble retrieved chunks into a prompt with clear instructions to answer
      only from provided context (and say "not found" if the answer isn't there)
- [ ] Call the LLM, return answer + cited chunk sources
- [ ] Write an integration test: two sessions with different docs, confirm no
      cross-session leakage in retrieval results

**Definition of Done:** Querying a session only ever returns answers grounded in
that session's own documents, verified by an automated test.

---

## Phase 5 — Evaluation & Accuracy Tuning

**Goal:** Prove the >90% accuracy target, don't just assert it.

- [ ] Source 3–5 real, public internal-knowledge-base-style documents
      (e.g. FastAPI/LangChain's own docs, a public engineering handbook) into
      `eval/test_docs/`, with `eval/test_docs/SOURCE.md` noting where each
      came from
- [ ] Build `/eval/qa_set.json` — 20 domain-specific Q&A pairs with expected
      answer or expected source chunk, written against those real test documents
- [ ] Build `/eval/run_eval.py` — runs all 20 questions through the live pipeline,
      scores each (LLM-as-judge or human-graded pass/fail), outputs accuracy %
- [ ] Run the eval, record baseline accuracy
- [ ] If below 90%: iterate on chunk size, retrieval `k`, or prompt — re-run eval
      after each change, and **log each iteration** (what changed, before/after
      accuracy) in `DESIGN.md` under an "Eval Iteration Log" section — this log
      is the single most interview-relevant artifact in the repo
- [ ] Add the eval script to CI as a regression check (fail build if accuracy
      drops below threshold on future changes)

**Definition of Done:** `run_eval.py` reports ≥90% accuracy, is wired into CI,
and the iteration log in `DESIGN.md` shows the reasoning behind the final
chunking/retrieval configuration.

---

## Phase 6 — Performance & Hardening

**Goal:** Meet the sub-second latency target and make the app production-safe.

- [ ] Measure p95 latency on `/query` under realistic load; tune HNSW index
      parameters (`m`, `ef_construction`, `ef_search`) if not sub-second
- [ ] Add request validation, rate limiting, and structured error responses
- [ ] Add structured logging: query latency, retrieval score, session id
      (no PII in logs)
- [ ] Load test with a 100-page document and concurrent sessions
- [ ] Final deploy to Vercel production, confirm all endpoints healthy

**Definition of Done:** p95 latency on `/query` is sub-second and logged/verified,
not assumed.

---

## Phase 7 — Documentation & Portfolio Polish

**Goal:** Someone reading the repo cold (e.g. an interviewer) understands what
was built, why key decisions were made, and can see it actually works.

- [ ] Finalize `DESIGN.md`: chunking strategy + rationale, index choice (HNSW
      vs IVFFlat) + rationale, session isolation approach, the eval iteration
      log from Phase 5, and known limitations/what you'd do differently at scale
- [ ] Finalize `README.md`: one-paragraph summary, live Vercel demo link,
      local quickstart (env setup → run), architecture diagram or description,
      and a "Results" section with **measured** accuracy % and p95 latency
- [ ] Add a short "Why these documents" note if using public docs as the
      knowledge-base source (ties back to the internal-KB framing)
- [ ] Do a final read-through as if you're an interviewer seeing the repo for
      the first time — confirm nothing requires tribal knowledge to follow

**Definition of Done:** A person with no prior context can read `README.md` +
`DESIGN.md`, understand the project and its tradeoffs, and try the live demo
without needing to ask you anything.

---

## Section 1 — Project Structure

```
documind/
├── app/
│   ├── main.py                # FastAPI app entrypoint, route registration
│   ├── config.py              # env var loading, settings
│   ├── api/
│   │   ├── documents.py       # POST /documents/upload
│   │   ├── sessions.py        # POST /sessions
│   │   └── query.py           # POST /query
│   ├── ingestion/
│   │   ├── loader.py          # LangChain document loaders
│   │   ├── chunker.py         # chunking logic
│   │   └── embedder.py        # embedding generation
│   ├── retrieval/
│   │   ├── search.py          # similarity search against pgvector
│   │   └── prompt.py          # prompt assembly for the LLM
│   ├── db/
│   │   ├── client.py          # Supabase client wrapper
│   │   └── schema.sql         # table + index definitions
│   └── models/
│       └── schemas.py         # Pydantic request/response models
├── eval/
│   ├── test_docs/              # real public docs used as the KB source
│   │   └── SOURCE.md           # where each test doc came from
│   ├── qa_set.json             # 20 curated Q&A pairs
│   └── run_eval.py             # eval harness
├── tests/
│   ├── test_chunker.py
│   ├── test_retrieval.py
│   └── test_session_isolation.py
├── .github/workflows/ci.yml
├── .env.example
├── vercel.json
├── requirements.txt
├── CLAUDE.md                   # persistent context, read every session
├── PLAN.md                     # phase-by-phase task list
├── DESIGN.md                   # decisions + rationale + eval iteration log
└── README.md                   # project summary, demo link, results
```

**Why this layout:**
- `api/` only handles HTTP concerns — request/response, no business logic
- `ingestion/` and `retrieval/` are the two core pipelines, kept fully separate
  so each can be tested and tuned independently
- `eval/` sits at the top level (not buried in `tests/`) because it's a product
  metric, not just a unit test — it should be runnable on its own
- `db/schema.sql` is the single source of truth for the schema — no
  schema-in-code drift

---

## Section 2 — Database Schema (Phase 2 reference)

```sql
create extension if not exists vector;

create table sessions (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz default now()
);

create table documents (
    id uuid primary key default gen_random_uuid(),
    session_id uuid references sessions(id) on delete cascade,
    filename text not null,
    page_count int,
    created_at timestamptz default now()
);

create table chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid references documents(id) on delete cascade,
    session_id uuid references sessions(id) on delete cascade,
    content text not null,
    embedding vector(1536),  -- match your embedding model's dimension
    metadata jsonb,
    created_at timestamptz default now()
);

create index on chunks using hnsw (embedding vector_cosine_ops);
create index on chunks (session_id);
```

---

## Notes for Claude Code

- Always run tests before marking a phase task complete.
- Don't introduce new dependencies not listed in Phase 1 without flagging it first.
- Keep chunk size/overlap and retrieval `k` as named constants in `config.py`,
  not hardcoded — Phase 5 will tune these.
- If a phase's Definition of Done can't be met, stop and report why rather than
  moving to the next phase with a workaround.