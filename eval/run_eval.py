"""DocuMind eval harness — the project's core metric.

Usage (from repo root):

    python -m eval.run_eval --ingest      # one-time: build the eval session
    python -m eval.run_eval               # retrieval accuracy (no LLM calls)
    python -m eval.run_eval --judge       # + answer accuracy via LLM judge

Two metrics, deliberately separate:

- retrieval accuracy (the >90% target): pass if the pair's
  expected_substring appears in any of the k retrieved chunks. Objective,
  costs only query embeddings, safe to run in CI on every change.
- answer accuracy (--judge): LLM-as-judge grades the end answer against
  the expected answer. Subjective-ish and quota-hungry (2 LLM calls per
  question on the free tier), so it's opt-in.

The eval session persists across runs (EVAL_SESSION_ID env var, or
eval/.session_id written by --ingest) so the corpus isn't re-embedded
every run — that would burn the free-tier quota for nothing.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    EMBEDDING_MODEL,
    LLM_MODEL,
    RETRIEVAL_K,
)

EVAL_DIR = Path(__file__).parent
SESSION_FILE = EVAL_DIR / ".session_id"
QA_SET = EVAL_DIR / "qa_set.json"
LAST_RUN = EVAL_DIR / "last_run.json"
JUDGE_PROGRESS = EVAL_DIR / ".judge_progress.json"
ACCURACY_THRESHOLD = 0.90

# Free tier is ~10 LLM requests/minute; --judge makes 2 per question.
JUDGE_PACE_SECONDS = 13

# The answer model's free tier is 20 requests/DAY — exactly one eval's
# worth of answers. Daily quotas are per-model, so the judge runs on a
# separate (lite) model to get its own 20/day budget, and progress is
# persisted so a mid-run quota failure resumes instead of restarting.
JUDGE_MODEL = "gemini-flash-lite-latest"

JUDGE_PROMPT = """You are grading a Q&A system. Question: {question}

Expected answer (ground truth): {expected}

System's answer: {actual}

Does the system's answer contain the same essential information as the
expected answer? Minor wording/format differences are fine; missing or
contradicting the key fact is a fail. Reply with exactly one word:
PASS or FAIL."""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def get_session_id() -> str:
    session_id = os.getenv("EVAL_SESSION_ID")
    if session_id:
        return session_id
    if SESSION_FILE.exists():
        return SESSION_FILE.read_text().strip()
    sys.exit("no eval session — run `python -m eval.run_eval --ingest` first")


def ingest_corpus() -> str:
    from app.db.client import get_client
    from app.ingestion.pipeline import ingest_file

    session_id = get_client().table("sessions").insert({}).execute().data[0]["id"]
    for pdf in sorted(EVAL_DIR.glob("test_docs/*.pdf")):
        print(f"ingesting {pdf.name} ...", flush=True)
        result = ingest_file(pdf, pdf.name, session_id)
        print(f"  {result.page_count} pages -> {result.chunk_count} chunks", flush=True)
    SESSION_FILE.write_text(session_id)
    print(f"eval session ready: {session_id} (saved to {SESSION_FILE})")
    return session_id


def eval_retrieval(session_id: str, qa_pairs: list[dict]) -> list[dict]:
    from app.retrieval.search import search_chunks

    results = []
    for i, qa in enumerate(qa_pairs, start=1):
        chunks = search_chunks(session_id, qa["question"])
        hit = any(
            _normalize(qa["expected_substring"]) in _normalize(c.content)
            for c in chunks
        )
        results.append(
            {
                "id": qa["id"],
                "question": qa["question"],
                "retrieval_pass": hit,
                "top_similarity": round(chunks[0].similarity, 4) if chunks else None,
            }
        )
        print(f"[{i:2}/{len(qa_pairs)}] {'PASS' if hit else 'FAIL'}  {qa['question']}")
    return results


def eval_answers(session_id: str, qa_pairs: list[dict], results: list[dict]) -> bool:
    """Answer + judge each pair, resuming from .judge_progress.json.
    Returns True once every pair has a verdict."""
    from langchain_core.messages import HumanMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    from app.config import GEMINI_API_KEY
    from app.retrieval.qa import answer_question

    judge = ChatGoogleGenerativeAI(
        model=JUDGE_MODEL, temperature=0.0, google_api_key=GEMINI_API_KEY
    )
    progress: dict = (
        json.loads(JUDGE_PROGRESS.read_text(encoding="utf-8"))
        if JUDGE_PROGRESS.exists()
        else {}
    )

    for qa, result in zip(qa_pairs, results):
        key = str(qa["id"])
        if key not in progress:
            try:
                answer = answer_question(session_id, qa["question"])
                time.sleep(JUDGE_PACE_SECONDS / 2)
                verdict = judge.invoke(
                    [
                        HumanMessage(
                            content=JUDGE_PROMPT.format(
                                question=qa["question"],
                                expected=qa["expected_answer"],
                                actual=answer.answer,
                            )
                        )
                    ]
                ).content
            except Exception as exc:  # noqa: BLE001 — any API failure: keep progress, exit cleanly
                print(f"[judge] stopping at q{key}: {exc}")
                print("[judge] progress saved; re-run --judge to resume")
                break
            progress[key] = {
                "answer": answer.answer,
                "answer_pass": "PASS" in str(verdict).upper(),
            }
            JUDGE_PROGRESS.write_text(json.dumps(progress, indent=2), encoding="utf-8")
            time.sleep(JUDGE_PACE_SECONDS / 2)
        result["answer"] = progress[key]["answer"]
        result["answer_pass"] = progress[key]["answer_pass"]
        print(f"[judge] {'PASS' if result['answer_pass'] else 'FAIL'}  {qa['question']}")

    return all(str(qa["id"]) in progress for qa in qa_pairs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ingest", action="store_true", help="build the eval session")
    parser.add_argument("--judge", action="store_true", help="also LLM-grade answers")
    args = parser.parse_args()

    if args.ingest:
        ingest_corpus()
        return

    session_id = get_session_id()
    qa_pairs = json.loads(QA_SET.read_text(encoding="utf-8"))
    results = eval_retrieval(session_id, qa_pairs)
    judge_complete = eval_answers(session_id, qa_pairs, results) if args.judge else False

    retrieval_acc = sum(r["retrieval_pass"] for r in results) / len(results)
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "chunk_size_tokens": CHUNK_SIZE_TOKENS,
            "chunk_overlap_tokens": CHUNK_OVERLAP_TOKENS,
            "retrieval_k": RETRIEVAL_K,
            "embedding_model": EMBEDDING_MODEL,
            "llm_model": LLM_MODEL,
        },
        "retrieval_accuracy": retrieval_acc,
        "results": results,
    }
    if judge_complete:
        summary["answer_accuracy"] = sum(r["answer_pass"] for r in results) / len(results)

    LAST_RUN.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nretrieval accuracy: {retrieval_acc:.0%} ({sum(r['retrieval_pass'] for r in results)}/{len(results)})")
    if judge_complete:
        print(f"answer accuracy:    {summary['answer_accuracy']:.0%}")
    elif args.judge:
        print("answer accuracy:    incomplete (quota) — re-run --judge to resume")
    print(f"details: {LAST_RUN}")

    if retrieval_acc < ACCURACY_THRESHOLD:
        sys.exit(f"FAIL: retrieval accuracy below {ACCURACY_THRESHOLD:.0%} threshold")


if __name__ == "__main__":
    main()
