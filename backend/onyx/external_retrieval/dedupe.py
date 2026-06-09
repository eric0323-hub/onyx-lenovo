from __future__ import annotations

from onyx.external_retrieval.models import NormalizedExternalRetrievalResult


def dedupe_external_retrieval_results(
    results: list[NormalizedExternalRetrievalResult],
) -> list[NormalizedExternalRetrievalResult]:
    deduped: dict[str, NormalizedExternalRetrievalResult] = {}

    for result in results:
        key = result.fact_key or result.canonical_key or result.dedupe_key
        existing = deduped.get(key)
        if existing is None or result.score > existing.score:
            deduped[key] = result

    return sorted(deduped.values(), key=lambda result: result.score, reverse=True)

