from onyx.external_retrieval.errors import ExternalRetrievalResponseError
from onyx.external_retrieval.models import ExternalRetrievalConfig
from onyx.external_retrieval.models import ExternalRetrievalSourceConfig
from onyx.external_retrieval.normalization import normalize_external_retrieval_response


def _source_config(**config_overrides: object) -> ExternalRetrievalSourceConfig:
    return ExternalRetrievalSourceConfig(
        id=7,
        name="Engineering Ontology",
        config=ExternalRetrievalConfig(
            endpoint="http://127.0.0.1:8000/api/retrieval/search",
            allow_localhost=True,
            **config_overrides,
        ),
    )


def test_normalizes_standard_response() -> None:
    normalized, invalid, warnings = normalize_external_retrieval_response(
        {
            "results": [
                {
                    "result_id": "result-1",
                    "canonical_key": "component:bms",
                    "fact_key": "component:bms|caused_by|issue:thermal",
                    "title": "Battery Management System failure causes",
                    "content": "  BMS failures are linked to thermal runaway.  ",
                    "url": "https://example.com/articles/bms",
                    "score": 0.86,
                    "confidence": 0.74,
                    "updated_at": "2026-05-20T10:00:00Z",
                    "source": {"source_id": "article-789"},
                }
            ]
        },
        _source_config(),
    )

    assert invalid == []
    assert warnings == []
    assert len(normalized) == 1
    result = normalized[0]
    assert result.title == "Battery Management System failure causes"
    assert result.content == "BMS failures are linked to thermal runaway."
    assert result.url == "https://example.com/articles/bms"
    assert result.score == 0.86
    assert result.confidence == 0.74
    assert result.document_id.startswith("external_retrieval:7:")
    assert result.metadata["external_source_name"] == "Engineering Ontology"


def test_normalizes_article_response() -> None:
    normalized, invalid, _ = normalize_external_retrieval_response(
        {
            "articles": [
                {
                    "article_title": "Battery failure analysis",
                    "article_url": "https://example.com/articles/battery",
                    "article": "Article evidence text",
                    "confidence": 82,
                }
            ]
        },
        _source_config(),
    )

    assert invalid == []
    assert normalized[0].title == "Battery failure analysis"
    assert normalized[0].content == "Article evidence text"
    assert normalized[0].confidence == 0.82
    assert normalized[0].score == 0.82


def test_preserves_relative_url_paths() -> None:
    normalized, invalid, _ = normalize_external_retrieval_response(
        {
            "results": [
                {
                    "title": "Relative source",
                    "content": "Evidence text",
                    "url": "docs/main/article.md",
                }
            ]
        },
        _source_config(),
    )

    assert invalid == []
    assert normalized[0].url == "docs/main/article.md"


def test_marks_missing_content_invalid() -> None:
    normalized, invalid, _ = normalize_external_retrieval_response(
        {
            "results": [
                {"title": "No evidence", "confidence": 0.9},
                {"title": "Valid", "content": "Evidence text"},
            ]
        },
        _source_config(),
    )

    assert len(normalized) == 1
    assert normalized[0].title == "Valid"
    assert len(invalid) == 1
    assert invalid[0].index == 0


def test_raises_when_all_results_missing_content() -> None:
    try:
        normalize_external_retrieval_response(
            {"results": [{"title": "No evidence"}]},
            _source_config(),
        )
    except ExternalRetrievalResponseError as e:
        assert "missing content" in str(e)
    else:
        raise AssertionError("Expected ExternalRetrievalResponseError")


def test_uses_configured_paths_and_score_scale() -> None:
    normalized, _, _ = normalize_external_retrieval_response(
        {"payload": {"items": [{"headline": "T", "body_text": "C", "rank": 43}]}},
        _source_config(
            result_path="$.payload.items",
            field_mapping={
                "title": ["$.headline"],
                "content": ["$.body_text"],
                "score": ["$.rank"],
            },
            score_scale=100,
        ),
    )

    assert normalized[0].title == "T"
    assert normalized[0].content == "C"
    assert normalized[0].score == 0.43
