from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session

from onyx.auth.users import current_curator_or_admin_user
from onyx.configs.constants import PUBLIC_API_TAGS
from onyx.db.document import delete_documents_complete
from onyx.db.document import get_document
from onyx.db.document import get_documents_by_cc_pair
from onyx.db.document import get_ingestion_documents
from onyx.db.engine.sql_engine import get_session
from onyx.db.models import User
from onyx.db.search_settings import get_active_search_settings
from onyx.document_index.factory import get_all_document_indices
from onyx.server.onyx_api.ingestion_service import upsert_ingestion_document
from onyx.server.onyx_api.models import DocMinimalInfo
from onyx.server.onyx_api.models import IngestionDocument
from onyx.server.onyx_api.models import IngestionResult
from onyx.server.utils_vector_db import require_vector_db
from onyx.utils.logger import setup_logger

logger = setup_logger()

# not using /api to avoid confusion with nginx api path routing
router = APIRouter(prefix="/onyx-api", tags=PUBLIC_API_TAGS)


@router.get("/connector-docs/{cc_pair_id}")
def get_docs_by_connector_credential_pair(
    cc_pair_id: int,
    _: User = Depends(current_curator_or_admin_user),
    db_session: Session = Depends(get_session),
) -> list[DocMinimalInfo]:
    db_docs = get_documents_by_cc_pair(cc_pair_id=cc_pair_id, db_session=db_session)
    return [
        DocMinimalInfo(
            document_id=doc.id,
            semantic_id=doc.semantic_id,
            link=doc.link,
        )
        for doc in db_docs
    ]


@router.get("/ingestion")
def get_ingestion_docs(
    _: User = Depends(current_curator_or_admin_user),
    db_session: Session = Depends(get_session),
) -> list[DocMinimalInfo]:
    db_docs = get_ingestion_documents(db_session)
    return [
        DocMinimalInfo(
            document_id=doc.id,
            semantic_id=doc.semantic_id,
            link=doc.link,
        )
        for doc in db_docs
    ]


@router.post("/ingestion", dependencies=[Depends(require_vector_db)])
def upsert_ingestion_doc(
    doc_info: IngestionDocument,
    _: User = Depends(current_curator_or_admin_user),
    db_session: Session = Depends(get_session),
) -> IngestionResult:
    try:
        result = upsert_ingestion_document(
            document_base=doc_info.document,
            db_session=db_session,
            cc_pair_id=doc_info.cc_pair_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    return IngestionResult(
        document_id=result.document_id,
        already_existed=result.already_existed,
    )


@router.delete("/ingestion/{document_id}", dependencies=[Depends(require_vector_db)])
def delete_ingestion_doc(
    document_id: str,
    _: User = Depends(current_curator_or_admin_user),
    db_session: Session = Depends(get_session),
) -> None:
    # Verify the document exists and was created via the ingestion API
    document = get_document(document_id=document_id, db_session=db_session)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.from_ingestion_api:
        raise HTTPException(
            status_code=400,
            detail="Document was not created via the ingestion API",
        )

    active_search_settings = get_active_search_settings(db_session)
    # This flow is for deletion so we get all indices.
    document_indices = get_all_document_indices(
        active_search_settings.primary,
        active_search_settings.secondary,
        None,
    )
    for document_index in document_indices:
        document_index.delete(
            document_id,
            chunk_count=document.chunk_count,
        )

    # Delete from database
    delete_documents_complete(db_session, [document_id])
