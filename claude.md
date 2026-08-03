# CLAUDE.md — Persistent Context for DocuMind

> This file loads automatically at the start of every Claude Code session.
> Keep it lean — only things that apply broadly, every session. Task-by-task
> work lives in `PLAN.md`, not here.

## What this project is

DocuMind is a **document Q&A tool for an internal knowledge base** — the kind
of tool a mid-size company would use to let employees ask questions against
internal docs (engineering runbooks, handbooks, technical docs) instead of
manually searching a wiki. This is a **portfolio project**: the goal isn't
just working code, it's a demo + repo that clearly demonstrates real RAG
engineering judgment to a technical interviewer.

That framing affects priorities:
- Favor clarity and documented tradeoffs over cleverness or premature scale.
- Every non-obvious decision (chunk size, index type, retrieval `k`) needs a
  one-line rationale comment or a line in `DESIGN.md` — not just the number.
- The eval methodology is a first-class deliverable, not a nice-to-have.

## How we work together

- Teach git as we go: explain the command or workflow when it matters, not just
  the result.
- Call out best practices when they affect the change, especially around diffs,
  branches, commits, and review hygiene.
- Before any commit, pause for a short quiz so I can confirm I understand what
  we changed and why.
- Keep the quiz lightweight and practical; focus on the current work, not trivia.
- If a faster path would skip a good learning moment, mention the tradeoff so I
  can choose deliberately.

## Stack (do not swap without discussion)

- Backend: Python, FastAPI
- Orchestration: LangChain
- Vector store: Supabase Postgres + pgvector (HNSW index, cosine distance)
- Deployment: Vercel (API), Supabase (DB)
- Embedding model and LLM provider: set in `app/config.py`, not hardcoded elsewhere

## Test/demo data

Test documents should be **realistic internal-knowledge-base material**, not
generic filler:
- Prefer real, public technical documentation (e.g. FastAPI's own docs,
  a public engineering handbook, or similar) so the demo is credible and
  reproducible by anyone reading the repo — no synthetic or made-up content.
- Store test documents in `eval/test_docs/` with a short `SOURCE.md` noting
  where each one came from (for attribution and reproducibility).

## Non-negotiable conventions

- Chunk size, overlap, and retrieval `k` are named constants in
  `app/config.py`. Never hardcode these inline.
- `ingestion/` and `retrieval/` stay fully decoupled — no retrieval logic in
  the ingestion pipeline or vice versa.
- Every session is isolated by `session_id` at the query layer, enforced in
  the similarity search filter — not just in application logic.
- Run relevant tests before marking any task complete:
  - Chunking changes → `pytest tests/test_chunker.py`
  - Retrieval changes → `pytest tests/test_retrieval.py tests/test_session_isolation.py`
  - Anything touching accuracy → `python eval/run_eval.py`
- Don't introduce new dependencies without flagging it first.

## The eval set is sacred

`eval/qa_set.json` (20 curated Q&A pairs) is the project's core metric. Any
change to chunking, embedding model, retrieval `k`, or prompt must be
re-validated against it via `eval/run_eval.py`, with the before/after accuracy
noted in the PR description or commit message. This log of "what moved the
number and why" is the most interview-relevant artifact in the whole repo —
don't let it go undocumented.

## Documentation deliverables (required, not optional)

- `DESIGN.md` — short doc explaining *why*, not just *what*: chunking
  strategy, index choice, session isolation approach, and what tradeoffs
  were considered. This is written for a technical reader deciding whether
  you understand RAG or just followed a tutorial.
- `README.md` — must include: what the project does, the live Vercel demo
  link, a quickstart, and a short "results" section stating the measured
  retrieval accuracy and p95 latency (not aspirational numbers — measured ones).

## What NOT to do

- Don't add LSP integrations, subagents, plugins, or MCP servers — this is a
  small greenfield project, not a large codebase; that tooling solves
  problems this project doesn't have.
- Don't optimize for scale beyond what's needed to prove the concept (100-page
  docs, sub-second search, >90% accuracy on the eval set). Gold-plating past
  that dilutes the portfolio story rather than strengthening it.
- Don't fabricate eval results or skip re-running `run_eval.py` after a
  retrieval-affecting change — an unverified accuracy claim is worse than a
  documented lower one.