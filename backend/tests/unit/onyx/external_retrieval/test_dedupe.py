from onyx.external_retrieval.dedupe import dedupe_external_retrieval_results
from onyx.external_retrieval.models import NormalizedExternalRetrievalResult


def _result(key: str, score: float) -> NormalizedExternalRetrievalResult:
    return NormalizedExternalRetrievalResult(
        index=0,
        title=f"Title {score}",
        content="content",
        score=score,
        dedupe_key=key,
        content_fingerprint=key,
        document_id=f"external_retrieval:1:{key}",
    )


def test_dedupe_keeps_highest_score() -> None:
    results = dedupe_external_retrieval_results(
        [_result("same", 0.2), _result("same", 0.9), _result("other", 0.5)]
    )

    assert [result.dedupe_key for result in results] == ["same", "other"]
    assert results[0].score == 0.9

