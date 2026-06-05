from datetime import datetime
from datetime import timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from onyx.configs.constants import DEFAULT_CC_PAIR_ID
from onyx.configs.constants import DocumentSource
from onyx.connectors.models import Document
from onyx.connectors.models import DocumentBase
from onyx.connectors.models import IndexAttemptMetadata
from onyx.db.connector_credential_pair import get_connector_credential_pair_from_id
from onyx.db.search_settings import get_active_search_settings
from onyx.db.search_settings import get_current_search_settings
from onyx.db.search_settings import get_secondary_search_settings
from onyx.document_index.factory import get_all_document_indices
from onyx.indexing.adapters.document_indexing_adapter import (
    DocumentIndexingBatchAdapter,
)
from onyx.indexing.embedder import DefaultIndexingEmbedder
from onyx.indexing.indexing_pipeline import IndexingPipelineResult
from onyx.indexing.indexing_pipeline import run_indexing_pipeline
from shared_configs.contextvars import get_current_tenant_id


class IngestionUpsertResult(BaseModel):
    document_id: str
    already_existed: bool


def prepare_ingestion_document(document_base: DocumentBase) -> Document:
    document_base.from_ingestion_api = True

    if document_base.doc_updated_at is None:
        document_base.doc_updated_at = datetime.now(tz=timezone.utc)

    document = Document.from_base(document_base)
    document.doc_metadata = document_base.doc_metadata
    document.external_access = document_base.external_access
    document.additional_info = document_base.additional_info
    document.parent_hierarchy_raw_node_id = document_base.parent_hierarchy_raw_node_id
    document.parent_hierarchy_node_id = document_base.parent_hierarchy_node_id

    # TODO once the frontend is updated with this enum, remove this logic
    if document.source == DocumentSource.INGESTION_API:
        document.source = DocumentSource.FILE

    return document


def index_ingestion_documents(
    *,
    documents: list[Document],
    db_session: Session,
    cc_pair_id: int | None = None,
) -> IndexingPipelineResult | None:
    if not documents:
        return None

    tenant_id = get_current_tenant_id()
    cc_pair = get_connector_credential_pair_from_id(
        db_session=db_session,
        cc_pair_id=cc_pair_id or DEFAULT_CC_PAIR_ID,
    )
    if cc_pair is None:
        raise ValueError("Connector-Credential Pair specified does not exist")

    active_search_settings = get_active_search_settings(db_session)
    search_settings = get_current_search_settings(db_session)
    index_embedding_model = DefaultIndexingEmbedder.from_db_search_settings(
        search_settings=search_settings
    )

    adapter = DocumentIndexingBatchAdapter(
        connector_id=cc_pair.connector_id,
        credential_id=cc_pair.credential_id,
        tenant_id=tenant_id,
        index_attempt_metadata=IndexAttemptMetadata(
            connector_id=cc_pair.connector_id,
            credential_id=cc_pair.credential_id,
        ),
    )

    primary_document_indices = get_all_document_indices(
        active_search_settings.primary,
        None,
        None,
    )
    indexing_pipeline_result = run_indexing_pipeline(
        embedder=index_embedding_model,
        document_indices=primary_document_indices,
        ignore_time_skip=True,
        db_session=db_session,
        tenant_id=tenant_id,
        document_batch=documents,
        request_id=None,
        adapter=adapter,
    )

    if active_search_settings.secondary:
        secondary_search_settings = get_secondary_search_settings(db_session)

        if secondary_search_settings is None:
            raise RuntimeError("Secondary index exists but no search settings configured")

        secondary_embedding_model = DefaultIndexingEmbedder.from_db_search_settings(
            search_settings=secondary_search_settings
        )
        secondary_document_indices = get_all_document_indices(
            active_search_settings.secondary,
            None,
            None,
        )
        run_indexing_pipeline(
            embedder=secondary_embedding_model,
            document_indices=secondary_document_indices,
            ignore_time_skip=True,
            db_session=db_session,
            tenant_id=tenant_id,
            document_batch=documents,
            request_id=None,
            adapter=adapter,
        )

    return indexing_pipeline_result


def upsert_ingestion_document(
    *,
    document_base: DocumentBase,
    db_session: Session,
    cc_pair_id: int | None = None,
) -> IngestionUpsertResult:
    document = prepare_ingestion_document(document_base)
    indexing_result = index_ingestion_documents(
        documents=[document],
        db_session=db_session,
        cc_pair_id=cc_pair_id,
    )
    if indexing_result is None:
        raise RuntimeError("No ingestion document was indexed")

    return IngestionUpsertResult(
        document_id=document.id,
        already_existed=indexing_result.new_docs == 0,
    )
