from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Response
from sqlalchemy.orm import Session

from onyx.auth.permissions import require_permission
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import Permission
from onyx.db.external_retrieval import create_external_retrieval_source
from onyx.db.external_retrieval import delete_external_retrieval_source
from onyx.db.external_retrieval import fetch_all_external_retrieval_sources
from onyx.db.external_retrieval import fetch_external_retrieval_source_by_id
from onyx.db.external_retrieval import update_external_retrieval_source
from onyx.db.models import ExternalRetrievalSource
from onyx.db.models import User
from onyx.external_retrieval.models import ExternalRetrievalAdapterType
from onyx.external_retrieval.models import ExternalRetrievalAuthType
from onyx.external_retrieval.models import ExternalRetrievalCallStrategy
from onyx.external_retrieval.models import ExternalRetrievalRequestMode
from onyx.external_retrieval.models import ExternalRetrievalSourceConfig
from onyx.external_retrieval.models import ExternalRetrievalTestRequest
from onyx.external_retrieval.normalization import (
    CONFIDENCE_PATH_FALLBACKS,
    CONTENT_PATH_FALLBACKS,
    SCORE_PATH_FALLBACKS,
    SOURCE_ID_PATH_FALLBACKS,
    TITLE_PATH_FALLBACKS,
    URL_PATH_FALLBACKS,
)
from onyx.external_retrieval.registry import get_external_retrieval_adapter
from onyx.external_retrieval.retrieval import source_config_from_db_model
from onyx.server.external_retrieval.models import ExternalRetrievalAdapterSchema
from onyx.server.external_retrieval.models import ExternalRetrievalDocumentSetView
from onyx.server.external_retrieval.models import ExternalRetrievalSourcePatchRequest
from onyx.server.external_retrieval.models import ExternalRetrievalSourceStatus
from onyx.server.external_retrieval.models import ExternalRetrievalSourceSummary
from onyx.server.external_retrieval.models import ExternalRetrievalSourceUpsertRequest
from onyx.server.external_retrieval.models import ExternalRetrievalSourceView
from onyx.server.external_retrieval.models import ExternalRetrievalTestConfigRequest
from onyx.server.external_retrieval.models import ExternalRetrievalTestResponse
from onyx.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(prefix="/external-retrieval")


def _source_document_sets(
    source: ExternalRetrievalSource,
) -> list[ExternalRetrievalDocumentSetView]:
    return [
        ExternalRetrievalDocumentSetView(
            id=mapping.document_set.id,
            name=mapping.document_set.name,
        )
        for mapping in source.document_sets
        if mapping.document_set is not None
    ]


def _source_view(source: ExternalRetrievalSource) -> ExternalRetrievalSourceView:
    source_config = source_config_from_db_model(source, include_credentials=False)
    return ExternalRetrievalSourceView(
        id=source.id,
        name=source.name,
        description=source.description,
        adapter_type=source_config.adapter_type,
        enabled=source.enabled,
        auth=source_config.auth,
        config=source_config.config,
        timeout_ms=source.timeout_ms,
        max_results=source.max_results,
        source_weight=source.source_weight,
        min_confidence=source.min_confidence,
        call_strategy=source_config.call_strategy,
        document_sets=_source_document_sets(source),
        time_created=source.time_created,
        time_updated=source.time_updated,
    )


def _source_summary(source: ExternalRetrievalSource) -> ExternalRetrievalSourceSummary:
    source_config = source_config_from_db_model(source, include_credentials=False)
    return ExternalRetrievalSourceSummary(
        id=source.id,
        name=source.name,
        description=source.description,
        adapter_type=source_config.adapter_type,
        enabled=source.enabled,
        endpoint=source_config.config.endpoint,
        timeout_ms=source.timeout_ms,
        max_results=source.max_results,
        source_weight=source.source_weight,
        min_confidence=source.min_confidence,
        call_strategy=source_config.call_strategy,
        document_sets=_source_document_sets(source),
        time_updated=source.time_updated,
    )


def _validate_source_config(source_config: ExternalRetrievalSourceConfig) -> None:
    adapter = get_external_retrieval_adapter(source_config.adapter_type)
    adapter.validate_config(source_config)


@router.get("/sources")
def list_external_retrieval_sources(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[ExternalRetrievalSourceSummary]:
    sources = fetch_all_external_retrieval_sources(db_session)
    return [_source_summary(source) for source in sources]


@router.post("/sources")
def create_external_retrieval_source_endpoint(
    request: ExternalRetrievalSourceUpsertRequest,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ExternalRetrievalSourceView:
    source_config = ExternalRetrievalSourceConfig(
        name=request.name,
        description=request.description,
        adapter_type=request.adapter_type,
        enabled=request.enabled,
        auth=request.auth,
        config=request.config,
        timeout_ms=request.timeout_ms,
        max_results=request.max_results,
        source_weight=request.source_weight,
        min_confidence=request.min_confidence,
        call_strategy=request.call_strategy,
    )
    try:
        _validate_source_config(source_config)
        source = create_external_retrieval_source(
            db_session=db_session,
            name=request.name,
            description=request.description,
            adapter_type=request.adapter_type,
            enabled=request.enabled,
            credentials=request.auth.model_dump(mode="json"),
            config=request.config.model_dump(mode="json"),
            timeout_ms=request.timeout_ms,
            max_results=request.max_results,
            source_weight=request.source_weight,
            min_confidence=request.min_confidence,
            call_strategy=request.call_strategy,
            created_by_user_id=user.id,
            document_set_ids=request.document_set_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.warning("Failed to create external retrieval source: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _source_view(source)


@router.get("/sources/{source_id}")
def get_external_retrieval_source_endpoint(
    source_id: int,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ExternalRetrievalSourceView:
    source = fetch_external_retrieval_source_by_id(db_session, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="External retrieval source not found")
    return _source_view(source)


@router.patch("/sources/{source_id}")
def patch_external_retrieval_source_endpoint(
    source_id: int,
    request: ExternalRetrievalSourcePatchRequest,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ExternalRetrievalSourceView:
    existing = fetch_external_retrieval_source_by_id(db_session, source_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="External retrieval source not found")

    current_config = source_config_from_db_model(existing, include_credentials=True)
    request_fields = request.model_fields_set
    source_config = ExternalRetrievalSourceConfig(
        id=source_id,
        name=request.name or current_config.name,
        description=(
            request.description
            if request.description is not None
            else current_config.description
        ),
        adapter_type=request.adapter_type or current_config.adapter_type,
        enabled=request.enabled if request.enabled is not None else current_config.enabled,
        auth=request.auth if request.auth_changed and request.auth else current_config.auth,
        config=request.config or current_config.config,
        timeout_ms=request.timeout_ms or current_config.timeout_ms,
        max_results=request.max_results or current_config.max_results,
        source_weight=request.source_weight or current_config.source_weight,
        min_confidence=(
            request.min_confidence
            if "min_confidence" in request_fields
            else current_config.min_confidence
        ),
        call_strategy=request.call_strategy or current_config.call_strategy,
    )
    try:
        _validate_source_config(source_config)
        source = update_external_retrieval_source(
            db_session=db_session,
            source_id=source_id,
            name=request.name,
            description=request.description,
            adapter_type=request.adapter_type,
            enabled=request.enabled,
            credentials=request.auth.model_dump(mode="json") if request.auth else None,
            credentials_changed=request.auth_changed,
            config=request.config.model_dump(mode="json") if request.config else None,
            timeout_ms=request.timeout_ms,
            max_results=request.max_results,
            source_weight=request.source_weight,
            min_confidence=(
                request.min_confidence
                if "min_confidence" in request_fields
                else current_config.min_confidence
            ),
            call_strategy=request.call_strategy,
            document_set_ids=request.document_set_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.warning("Failed to update external retrieval source: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _source_view(source)


@router.delete("/sources/{source_id}", status_code=204, response_class=Response)
def delete_external_retrieval_source_endpoint(
    source_id: int,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> Response:
    if not delete_external_retrieval_source(db_session, source_id):
        raise HTTPException(status_code=404, detail="External retrieval source not found")
    return Response(status_code=204)


@router.post("/sources/{source_id}/validate")
def validate_external_retrieval_source_endpoint(
    source_id: int,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> dict[str, str]:
    source = fetch_external_retrieval_source_by_id(db_session, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="External retrieval source not found")
    try:
        _validate_source_config(source_config_from_db_model(source, include_credentials=True))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok"}


@router.post("/sources/{source_id}/test")
def test_external_retrieval_source_endpoint(
    source_id: int,
    request: ExternalRetrievalTestRequest,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ExternalRetrievalTestResponse:
    source = fetch_external_retrieval_source_by_id(db_session, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="External retrieval source not found")
    source_config = source_config_from_db_model(source, include_credentials=True)
    adapter = get_external_retrieval_adapter(source_config.adapter_type)
    return adapter.test(request, source_config)


@router.post("/sources/test-config")
def test_external_retrieval_config_endpoint(
    request: ExternalRetrievalTestConfigRequest,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> ExternalRetrievalTestResponse:
    source_config = ExternalRetrievalSourceConfig(
        name=request.name,
        description=request.description,
        adapter_type=request.adapter_type,
        enabled=request.enabled,
        auth=request.auth,
        config=request.config,
        timeout_ms=request.timeout_ms,
        max_results=request.max_results,
        source_weight=request.source_weight,
        min_confidence=request.min_confidence,
        call_strategy=request.call_strategy,
    )
    adapter = get_external_retrieval_adapter(source_config.adapter_type)
    return adapter.test(request.test, source_config)


@router.get("/adapter-schemas")
def get_external_retrieval_adapter_schemas(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> ExternalRetrievalAdapterSchema:
    return ExternalRetrievalAdapterSchema(
        adapter_types=[adapter_type.value for adapter_type in ExternalRetrievalAdapterType],
        auth_types=[auth_type.value for auth_type in ExternalRetrievalAuthType],
        request_modes=[mode.value for mode in ExternalRetrievalRequestMode],
        call_strategies=[strategy.value for strategy in ExternalRetrievalCallStrategy],
        default_field_mapping={
            "title": TITLE_PATH_FALLBACKS,
            "content": CONTENT_PATH_FALLBACKS,
            "url": URL_PATH_FALLBACKS,
            "score": SCORE_PATH_FALLBACKS,
            "confidence": CONFIDENCE_PATH_FALLBACKS,
            "source_id": SOURCE_ID_PATH_FALLBACKS,
        },
    )


@router.get("/sources/{source_id}/status")
def get_external_retrieval_source_status(
    source_id: int,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ExternalRetrievalSourceStatus:
    source = fetch_external_retrieval_source_by_id(db_session, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="External retrieval source not found")
    return ExternalRetrievalSourceStatus(
        id=source.id,
        enabled=source.enabled,
        status="enabled" if source.enabled else "disabled",
    )
