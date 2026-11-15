"""Measure evidence retrieval on the labelled query set. Offline and deterministic.

Usage, from `ai_agent/`:

    python -m scripts.evaluate_retrieval             # current scoring
    python -m scripts.evaluate_retrieval --legacy    # scoring rules of the first version
    python -m scripts.evaluate_retrieval --corpus path/to/another_corpus.json

The queries and their relevant entries are in `tests/fixtures/retrieval_queries.json`.
Relevance was judged by the author of the corpus, so these numbers describe consistency
with one person's judgement, not an independent benchmark.

Measures, over the top 3 results (the number the agent shows):

- hit rate: share of supported queries with at least one relevant entry in the top 3;
- precision: share of returned entries that are relevant;
- reciprocal rank: mean of 1 / rank of the first relevant entry (0 when none);
- sources: mean number of distinct sources among the returned entries;
- unsupported: share of out-of-corpus queries that correctly return nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from orbit_agent.evidence.store import DEFAULT_CORPUS_PATH, EvidenceStore

QUERIES_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "retrieval_queries.json"
TOP_K = 3


def evaluate(store: EvidenceStore, *, legacy: bool = False) -> dict[str, Any]:
    """Return per-category and overall measures for `store`."""
    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))["queries"]
    known = {passage.evidence_id for passage in store.passages}
    rows: dict[str, list[dict[str, float]]] = defaultdict(list)
    unsupported_total = unsupported_empty = 0
    details = []
    for item in queries:
        results = store.search(item["query"], top_k=TOP_K, legacy=legacy)
        returned = [result.passage.evidence_id for result in results]
        if item["category"] == "unsupported":
            unsupported_total += 1
            unsupported_empty += not returned
            details.append({"id": item["id"], "returned": returned, "hit": not returned})
            continue
        relevant = set(item["relevant"])
        hits = [evidence_id in relevant for evidence_id in returned]
        first = next((rank for rank, hit in enumerate(hits, start=1) if hit), None)
        rows[item["category"]].append(
            {
                "hit": float(any(hits)),
                "precision": sum(hits) / len(hits) if hits else 0.0,
                "reciprocal_rank": 1 / first if first else 0.0,
                "sources": float(len({result.passage.url for result in results})),
                # Whether the corpus holds any entry judged relevant for this query.
                "answerable": float(bool(relevant & known)),
            }
        )
        details.append({"id": item["id"], "returned": returned, "hit": any(hits)})

    def mean(values: list[dict[str, float]], key: str) -> float:
        return round(sum(row[key] for row in values) / len(values), 3) if values else 0.0

    everything = [row for values in rows.values() for row in values]
    measures = ("hit", "precision", "reciprocal_rank", "sources", "answerable")
    return {
        "corpus_id": store.corpus_id,
        "entries": len(store.passages),
        "scoring": "legacy" if legacy else "current",
        "supported_queries": len(everything),
        "overall": {key: mean(everything, key) for key in measures},
        "by_category": {
            category: {"queries": len(values), **{key: mean(values, key) for key in measures}}
            for category, values in sorted(rows.items())
        },
        "unsupported": {
            "queries": unsupported_total,
            "correctly_empty": unsupported_empty,
        },
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--legacy", action="store_true", help="use the first version's scoring")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    arguments = parser.parse_args()
    report = evaluate(EvidenceStore.load(arguments.corpus), legacy=arguments.legacy)
    if arguments.json:
        print(json.dumps(report, indent=2))
        return 0
    overall = report["overall"]
    print(
        f"{report['corpus_id']}: {report['entries']} entries, scoring={report['scoring']}, "
        f"{report['supported_queries']} supported queries, top {TOP_K}"
    )
    print(f"{'category':<16}{'n':>3}{'hit':>8}{'prec':>8}{'rr':>8}{'sources':>9}{'answerable':>12}")
    for category, row in report["by_category"].items():
        print(
            f"{category:<16}{row['queries']:>3}{row['hit']:>8.2f}{row['precision']:>8.2f}"
            f"{row['reciprocal_rank']:>8.2f}{row['sources']:>9.2f}{row['answerable']:>12.2f}"
        )
    print(
        f"{'ALL':<16}{report['supported_queries']:>3}{overall['hit']:>8.2f}"
        f"{overall['precision']:>8.2f}{overall['reciprocal_rank']:>8.2f}"
        f"{overall['sources']:>9.2f}{overall['answerable']:>12.2f}"
    )
    unsupported = report["unsupported"]
    print(
        f"unsupported queries returning nothing: {unsupported['correctly_empty']}/"
        f"{unsupported['queries']}"
    )
    misses = [row["id"] for row in report["details"] if not row["hit"]]
    print("misses:", ", ".join(misses) if misses else "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
