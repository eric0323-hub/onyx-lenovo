from __future__ import annotations

from uuid import uuid4

from onyx.configs.constants import DocumentSource
from onyx.context.search.models import ChunkSearchRequest
from onyx.context.search.models import IndexFilters
from onyx.context.search.models import InferenceChunk
from onyx.context.search.pipeline import search_pipeline
from onyx.db.models import User
from onyx.taxonomy.models import TaxonomySearchDecision
from onyx.taxonomy.models import TaxonomySearchMode
from onyx.taxonomy.models import TaxonomySearchRecommendedAction


def _chunk(document_id: str, score: float) -> InferenceChunk:
    return InferenceChunk(
        document_id=document_id,
        chunk_id=0,
        content=f"{document_id} content",
        source_type=DocumentSource.WEB,
        semantic_identifier=document_id,
        title=document_id,
        boost=0,
        score=score,
        hidden=False,
        metadata={},
        match_highlights=[],
        doc_summary="",
        chunk_context="",
        updated_at=None,
        image_file_id=None,
        source_links={},
        section_continuation=False,
        blurb=document_id,
    )


def _user() -> User:
    return User(id=uuid4(), email="user@example.com")


def test_search_pipeline_merges_taxonomy_branch_when_leaf_matches(monkeypatch) -> None:
    calls: list[IndexFilters] = []

    def fake_search_chunks(**kwargs):  # noqa: ANN001
        filters = kwargs["query_request"].filters
        calls.append(filters)
        if filters.taxonomy_leaf_ids:
            return [_chunk("taxonomy-only", 0.95), _chunk("shared", 0.8)]
        return [_chunk("normal", 0.9), _chunk("shared", 0.7)]

    monkeypatch.setattr("onyx.context.search.pipeline.search_chunks", fake_search_chunks)
    monkeypatch.setattr(
        "onyx.context.search.pipeline.get_query_embedding", lambda *_, **__: [1.0, 0.0]
    )
    monkeypatch.setattr(
        "onyx.context.search.pipeline.load_settings",
        lambda: type(
            "Settings",
            (),
            {
                "taxonomy_search_enabled": True,
                "taxonomy_search_mode": TaxonomySearchMode.SOFT_FILTER_WITH_FALLBACK,
            },
        )(),
    )
    monkeypatch.setattr(
        "onyx.context.search.pipeline.match_taxonomy_query",
        lambda **_: TaxonomySearchDecision(
            matched=True,
            node_id="leaf-1",
            confidence=0.9,
            expanded_leaf_ids=["leaf-1"],
            recommended_action=TaxonomySearchRecommendedAction.AUGMENT_SEARCH,
        ),
    )
    monkeypatch.setattr(
        "onyx.context.search.pipeline.build_access_filters_for_user", lambda *_, **__: []
    )
    monkeypatch.setattr(
        "onyx.context.search.pipeline.fetch_ee_implementation_or_noop",
        lambda *_, **__: lambda chunks, user: chunks,  # noqa: ARG005
    )

    chunks = search_pipeline(
        chunk_search_request=ChunkSearchRequest(query="年假怎么申请", limit=10),
        document_index=None,  # type: ignore[arg-type]
        user=_user(),
        persona_search_info=None,
        db_session=object(),  # type: ignore[arg-type]
        prefetched_federated_retrieval_infos=[],
    )

    assert len(calls) == 2
    assert calls[0].taxonomy_leaf_ids is None
    assert calls[1].taxonomy_leaf_ids == ["leaf-1"]
    assert [chunk.document_id for chunk in chunks] == [
        "taxonomy-only",
        "normal",
        "shared",
    ]
    assert next(chunk for chunk in chunks if chunk.document_id == "shared").score == 0.8


def test_search_pipeline_does_not_run_taxonomy_branch_without_leaf_match(
    monkeypatch,
) -> None:
    calls: list[IndexFilters] = []

    def fake_search_chunks(**kwargs):  # noqa: ANN001
        filters = kwargs["query_request"].filters
        calls.append(filters)
        return [_chunk("normal", 0.9)]

    monkeypatch.setattr("onyx.context.search.pipeline.search_chunks", fake_search_chunks)
    monkeypatch.setattr(
        "onyx.context.search.pipeline.get_query_embedding", lambda *_, **__: [1.0, 0.0]
    )
    monkeypatch.setattr(
        "onyx.context.search.pipeline.load_settings",
        lambda: type(
            "Settings",
            (),
            {
                "taxonomy_search_enabled": True,
                "taxonomy_search_mode": TaxonomySearchMode.SOFT_FILTER_WITH_FALLBACK,
            },
        )(),
    )
    monkeypatch.setattr(
        "onyx.context.search.pipeline.match_taxonomy_query",
        lambda **_: TaxonomySearchDecision(
            matched=False,
            recommended_action=TaxonomySearchRecommendedAction.NONE,
        ),
    )
    monkeypatch.setattr(
        "onyx.context.search.pipeline.build_access_filters_for_user", lambda *_, **__: []
    )
    monkeypatch.setattr(
        "onyx.context.search.pipeline.fetch_ee_implementation_or_noop",
        lambda *_, **__: lambda chunks, user: chunks,  # noqa: ARG005
    )

    chunks = search_pipeline(
        chunk_search_request=ChunkSearchRequest(query="泛泛的问题", limit=10),
        document_index=None,  # type: ignore[arg-type]
        user=_user(),
        persona_search_info=None,
        db_session=object(),  # type: ignore[arg-type]
        prefetched_federated_retrieval_infos=[],
    )

    assert len(calls) == 1
    assert calls[0].taxonomy_leaf_ids is None
    assert [chunk.document_id for chunk in chunks] == ["normal"]
