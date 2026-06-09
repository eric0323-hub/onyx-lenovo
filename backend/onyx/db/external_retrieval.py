from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from onyx.db.models import DocumentSet
from onyx.db.models import ExternalRetrievalSource
from onyx.db.models import ExternalRetrievalSource__DocumentSet
from onyx.external_retrieval.models import ExternalRetrievalAdapterType
from onyx.external_retrieval.models import ExternalRetrievalCallStrategy
from onyx.utils.encryption import reject_masked_credentials

_UNSET = object()


def fetch_external_retrieval_source_by_id(
    db_session: Session,
    source_id: int,
) -> ExternalRetrievalSource | None:
    stmt = (
        select(ExternalRetrievalSource)
        .options(
            selectinload(ExternalRetrievalSource.document_sets).selectinload(
                ExternalRetrievalSource__DocumentSet.document_set
            )
        )
        .where(ExternalRetrievalSource.id == source_id)
    )
    return db_session.scalars(stmt).first()


def fetch_external_retrieval_source_by_name(
    db_session: Session,
    name: str,
) -> ExternalRetrievalSource | None:
    stmt = select(ExternalRetrievalSource).where(
        ExternalRetrievalSource.name.ilike(name)
    )
    return db_session.scalars(stmt).first()


def fetch_all_external_retrieval_sources(
    db_session: Session,
) -> list[ExternalRetrievalSource]:
    stmt = (
        select(ExternalRetrievalSource)
        .options(
            selectinload(ExternalRetrievalSource.document_sets).selectinload(
                ExternalRetrievalSource__DocumentSet.document_set
            )
        )
        .order_by(ExternalRetrievalSource.id.asc())
    )
    return list(db_session.scalars(stmt).all())


def check_external_retrieval_sources_exist(db_session: Session) -> bool:
    stmt = select(ExternalRetrievalSource.id).limit(1)
    return db_session.execute(stmt).first() is not None


def _ensure_unique_name(
    db_session: Session,
    name: str,
    source_id: int | None,
) -> None:
    existing = fetch_external_retrieval_source_by_name(db_session, name)
    if existing is not None and existing.id != source_id:
        raise ValueError(f"An external retrieval source named '{name}' already exists.")


def _replace_document_set_mappings(
    db_session: Session,
    source: ExternalRetrievalSource,
    document_set_ids: list[int],
) -> None:
    if source.id is None:
        raise ValueError("Cannot map document sets before source has an id.")

    db_session.execute(
        delete(ExternalRetrievalSource__DocumentSet).where(
            ExternalRetrievalSource__DocumentSet.external_retrieval_source_id
            == source.id
        )
    )

    for document_set_id in sorted(set(document_set_ids)):
        document_set = db_session.get(DocumentSet, document_set_id)
        if document_set is None:
            raise ValueError(f"Document set {document_set_id} does not exist.")
        db_session.add(
            ExternalRetrievalSource__DocumentSet(
                external_retrieval_source_id=source.id,
                document_set_id=document_set_id,
                config={},
            )
        )


def create_external_retrieval_source(
    *,
    db_session: Session,
    name: str,
    description: str | None,
    adapter_type: ExternalRetrievalAdapterType,
    enabled: bool,
    credentials: dict[str, Any] | None,
    config: dict[str, Any],
    timeout_ms: int,
    max_results: int,
    source_weight: float,
    min_confidence: float | None,
    call_strategy: ExternalRetrievalCallStrategy,
    created_by_user_id: UUID | None,
    document_set_ids: list[int],
) -> ExternalRetrievalSource:
    _ensure_unique_name(db_session, name, None)
    if credentials is not None:
        reject_masked_credentials(credentials)

    source = ExternalRetrievalSource(
        name=name,
        description=description,
        adapter_type=adapter_type.value,
        enabled=enabled,
        credentials=credentials,  # ty: ignore[invalid-assignment]
        config=config,
        timeout_ms=timeout_ms,
        max_results=max_results,
        source_weight=source_weight,
        min_confidence=min_confidence,
        call_strategy=call_strategy.value,
        created_by_user_id=created_by_user_id,
    )
    db_session.add(source)
    db_session.flush()
    _replace_document_set_mappings(db_session, source, document_set_ids)
    db_session.commit()
    db_session.refresh(source)
    return source


def update_external_retrieval_source(
    *,
    db_session: Session,
    source_id: int,
    name: str | None = None,
    description: str | None = None,
    adapter_type: ExternalRetrievalAdapterType | None = None,
    enabled: bool | None = None,
    credentials: dict[str, Any] | None = None,
    credentials_changed: bool = False,
    config: dict[str, Any] | None = None,
    timeout_ms: int | None = None,
    max_results: int | None = None,
    source_weight: float | None = None,
    min_confidence: float | None | object = _UNSET,
    call_strategy: ExternalRetrievalCallStrategy | None = None,
    document_set_ids: list[int] | None = None,
) -> ExternalRetrievalSource:
    source = fetch_external_retrieval_source_by_id(db_session, source_id)
    if source is None:
        raise ValueError(f"No external retrieval source with id {source_id} exists.")

    if name is not None:
        _ensure_unique_name(db_session, name, source_id)
        source.name = name
    if description is not None:
        source.description = description
    if adapter_type is not None:
        source.adapter_type = adapter_type.value
    if enabled is not None:
        source.enabled = enabled
    if credentials_changed:
        if credentials is not None:
            reject_masked_credentials(credentials)
        source.credentials = credentials  # ty: ignore[invalid-assignment]
    if config is not None:
        source.config = config
    if timeout_ms is not None:
        source.timeout_ms = timeout_ms
    if max_results is not None:
        source.max_results = max_results
    if source_weight is not None:
        source.source_weight = source_weight
    if min_confidence is not _UNSET:
        source.min_confidence = min_confidence  # ty: ignore[assignment]
    if call_strategy is not None:
        source.call_strategy = call_strategy.value
    if document_set_ids is not None:
        _replace_document_set_mappings(db_session, source, document_set_ids)

    db_session.commit()
    db_session.refresh(source)
    return source


def delete_external_retrieval_source(
    db_session: Session,
    source_id: int,
) -> bool:
    source = fetch_external_retrieval_source_by_id(db_session, source_id)
    if source is None:
        return False
    db_session.delete(source)
    db_session.commit()
    return True


def fetch_enabled_external_retrieval_sources_for_document_sets(
    db_session: Session,
    document_set_names: list[str] | None,
) -> list[ExternalRetrievalSource]:
    if not document_set_names:
        return []

    stmt = (
        select(ExternalRetrievalSource)
        .join(ExternalRetrievalSource__DocumentSet)
        .join(DocumentSet)
        .options(
            joinedload(ExternalRetrievalSource.document_sets).joinedload(
                ExternalRetrievalSource__DocumentSet.document_set
            )
        )
        .where(
            ExternalRetrievalSource.enabled.is_(True),
            DocumentSet.name.in_(document_set_names),
        )
        .order_by(ExternalRetrievalSource.id.asc())
    )
    return list(db_session.scalars(stmt).unique().all())
