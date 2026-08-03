"""Measure semantic-search latency (the sub-second p95 target).

Runs the real retrieval path — Gemini query embedding + pgvector
match_chunks over the eval corpus (362 chunks) — N times sequentially
and then under concurrency, reporting p50/p95/max per component.

The LLM generation step is deliberately excluded: the success criterion
targets search latency, and generation time is a property of the LLM
provider, not our retrieval design. Full /query timing is reported in
README from production once quota allows.

Usage (repo root):  python -m scripts.measure_latency [--n 30] [--concurrency 8]
"""

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.db.client import get_client
from app.embeddings import embed_texts
from app.retrieval.search import search_chunks


def pctl(values: list[float], p: float) -> float:
    return statistics.quantiles(values, n=100)[int(p) - 1] if len(values) > 1 else values[0]


def report(name: str, ms: list[float]) -> None:
    print(
        f"{name:22} p50={pctl(ms, 50):7.0f}ms  p95={pctl(ms, 95):7.0f}ms  "
        f"max={max(ms):7.0f}ms  (n={len(ms)})"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()

    session_id = (Path("eval") / ".session_id").read_text().strip()
    questions = [q["question"] for q in json.loads(Path("eval/qa_set.json").read_text(encoding="utf-8"))]

    embed_ms, rpc_ms, total_ms = [], [], []
    client = get_client()

    print(f"sequential x{args.n} against eval session ({session_id[:8]}…)\n")
    for i in range(args.n):
        q = questions[i % len(questions)]

        t0 = time.perf_counter()
        [vec] = embed_texts([q])
        t1 = time.perf_counter()
        client.rpc(
            "match_chunks",
            {"query_embedding": vec, "match_session_id": session_id, "match_count": 4},
        ).execute()
        t2 = time.perf_counter()

        embed_ms.append((t1 - t0) * 1000)
        rpc_ms.append((t2 - t1) * 1000)
        total_ms.append((t2 - t0) * 1000)

    report("query embedding", embed_ms)
    report("pgvector search", rpc_ms)
    report("search end-to-end", total_ms)

    print(f"\nconcurrent: {args.concurrency} workers x {args.n} searches\n")
    conc_ms = []

    def one(i: int) -> float:
        t0 = time.perf_counter()
        search_chunks(session_id, questions[i % len(questions)])
        return (time.perf_counter() - t0) * 1000

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        conc_ms = list(pool.map(one, range(args.n)))
    report("search (concurrent)", conc_ms)

    verdict = "PASS" if pctl(total_ms, 95) < 1000 else "FAIL"
    print(f"\nsub-second p95 target: {verdict}")


if __name__ == "__main__":
    main()
