from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from sqlalchemy.orm import Session

from onyx.configs.constants import DocumentSource
from onyx.context.search.models import InferenceChunk
from onyx.db.external_retrieval import (
    fetch_enabled_external_retrieval_sources_for_document_sets,
)
from onyx.db.models import ExternalRetrievalSource
from onyx.external_retrieval.models import ExternalRetrievalAdapterType
from onyx.external_retrieval.models import ExternalRetrievalAuthConfig
from onyx.external_retrieval.models import ExternalRetrievalCallStrategy
from onyx.external_retrieval.models import ExternalRetrievalConfig
from onyx.external_retrieval.models import ExternalRetrievalRequest
from onyx.external_retrieval.models import ExternalRetrievalSourceConfig
from onyx.external_retrieval.models import NormalizedExternalRetrievalResult
from onyx.external_retrieval.registry import get_external_retrieval_adapter
from onyx.utils.logger import setup_logger

logger = setup_logger()


class ExternalRetrievalInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_id: int
    source_name: str
    call_strategy: ExternalRetrievalCallStrategy
    source_weight: float
    retrieval_function: Callable[[str], list[InferenceChunk]]


def source_config_from_db_model(
    source: ExternalRetrievalSource,
    *,
    include_credentials: bool,
) -> ExternalRetrievalSourceConfig:
    credentials: dict[str, Any] = {}
    if source.credentials is not None:
        raw_credentials = source.credentials.get_value(apply_mask=False)
        credentials = (
            raw_credentials
            if include_credentials
            else _mask_external_retrieval_auth(raw_credentials)
        )

    return ExternalRetrievalSourceConfig(
        id=source.id,
        name=source.name,
        description=source.description,
        adapter_type=ExternalRetrievalAdapterType(source.adapter_type),
        enabled=source.enabled,
        auth=ExternalRetrievalAuthConfig.model_validate(credentials or {}),
        config=ExternalRetrievalConfig.model_validate(source.config or {}),
        timeout_ms=source.timeout_ms,
        max_results=source.max_results,
        source_weight=source.source_weight,
        min_confidence=source.min_confidence,
        call_strategy=ExternalRetrievalCallStrategy(source.call_strategy),
    )


def _mask_external_retrieval_auth(credentials: dict[str, Any]) -> dict[str, Any]:
    masked = dict(credentials)
    for key in ("token", "api_key", "password"):
        value = masked.get(key)
        if isinstance(value, str) and value:
            masked[key] = "••••••••••••"
    return masked


def inference_chunk_from_external_result(
    result: NormalizedExternalRetrievalResult,
    *,
    source_config: ExternalRetrievalSourceConfig,
) -> InferenceChunk:
    return InferenceChunk(
        chunk_id=0,
        blurb=result.content[:512],
        content=result.content,
        source_links={0: result.url} if result.url else None,
        image_file_id=None,
        section_continuation=False,
        document_id=result.document_id,
        source_type=DocumentSource.EXTERNAL_RETRIEVAL,
        semantic_identifier=result.title,
        title=result.title,
        boost=0,
        score=result.score * source_config.source_weight,
        hidden=False,
        metadata=result.metadata,
        match_highlights=[],
        doc_summary="",
        chunk_context="",
        updated_at=result.updated_at,
        primary_owners=None,
        secondary_owners=None,
        is_federated=True,
    )


def _build_retrieval_function(
    source_config: ExternalRetrievalSourceConfig,
    *,
    user_id: UUID | None,
    tenant_id: str | None,
    document_set_names: list[str] | None,
) -> Callable[[str], list[InferenceChunk]]:
    adapter = get_external_retrieval_adapter(source_config.adapter_type)

    def retrieval_function(query: str) -> list[InferenceChunk]:
        normalized_results = adapter.search(
            ExternalRetrievalRequest(
                query=query,
                limit=source_config.max_results,
                document_set_names=document_set_names,
                user_id=user_id,
                tenant_id=tenant_id,
            ),
            source_config,
        )
        return [
            inference_chunk_from_external_result(
                result,
                source_config=source_config,
            )
            for result in normalized_results
        ]

    return retrieval_function


def get_external_retrieval_functions(
    db_session: Session,
    user_id: UUID | None,
    document_set_names: list[str] | None,
    tenant_id: str | None,
) -> list[ExternalRetrievalInfo]:
    sources = fetch_enabled_external_retrieval_sources_for_document_sets(
        db_session=db_session,
        document_set_names=document_set_names,
    )
    retrieval_infos: list[ExternalRetrievalInfo] = []
    for source in sources:
        source_config = source_config_from_db_model(source, include_credentials=True)
        if (
            source_config.call_strategy
            != ExternalRetrievalCallStrategy.ORIGINAL_QUERY_ONCE
        ):
            logger.warning(
                "Skipping external retrieval source %s with unsupported call_strategy=%s",
                source.id,
                source_config.call_strategy,
            )
            continue

        retrieval_infos.append(
            ExternalRetrievalInfo(
                source_id=source.id,
                source_name=source.name,
                call_strategy=source_config.call_strategy,
                source_weight=source_config.source_weight,
                retrieval_function=_build_retrieval_function(
                    source_config,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    document_set_names=document_set_names,
                ),
            )
        )

    return retrieval_infos
