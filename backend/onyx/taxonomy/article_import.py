from __future__ import annotations

from datetime import datetime
from datetime import timezone
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from onyx.configs.constants import DocumentSource
from onyx.connectors.file.connector import LocalFileConnector
from onyx.connectors.models import Document
from onyx.connectors.models import HierarchyNode
from onyx.db.enums import TaxonomySummaryStatus
from onyx.db.taxonomy import get_document_ids_missing_complete_summary
from onyx.db.taxonomy import upsert_document_summary
from onyx.file_processing.extract_file_text import get_file_ext
from onyx.server.onyx_api.ingestion_service import index_ingestion_documents
from onyx.taxonomy.service import generate_summaries_for_documents
from onyx.utils.logger import setup_logger

logger = setup_logger()

SUPPORTED_ARTICLE_IMPORT_EXTENSIONS = {".md", ".markdown", ".pdf"}


class TaxonomyArticleImportFile(BaseModel):
    file_id: str
    file_name: str


def safe_taxonomy_article_file_name(file_name: str | None) -> str | None:
    if not file_name:
        return None
    return Path(file_name).name


def validate_taxonomy_article_file_name(file_name: str | None) -> str:
    safe_file_name = safe_taxonomy_article_file_name(file_name)
    if not safe_file_name:
        raise ValueError("文件名不能为空")

    extension = get_file_ext(safe_file_name)
    if extension not in SUPPORTED_ARTICLE_IMPORT_EXTENSIONS:
        raise ValueError("仅支持 Markdown 和 PDF 文件")

    return safe_file_name


def load_taxonomy_article_documents_from_file_store(
    *,
    file_id: str,
    file_name: str,
) -> list[Document]:
    connector = LocalFileConnector(
        file_locations=[file_id],
        file_names=[file_name],
    )
    connector.load_credentials({})

    documents: list[Document] = []
    for batch in connector.load_from_state():
        documents.extend([doc for doc in batch if not isinstance(doc, HierarchyNode)])
    return documents


def prepare_taxonomy_article_documents(
    *,
    file_id: str,
    file_name: str,
    documents: list[Document],
    created_by_user_id: UUID | str | None,
) -> list[Document]:
    imported_documents: list[Document] = []
    now = datetime.now(timezone.utc)

    for index, document in enumerate(documents):
        document.id = (
            f"taxonomy_article__{file_id}"
            if index == 0
            else f"taxonomy_article__{file_id}__{index}"
        )
        document.source = DocumentSource.FILE
        document.from_ingestion_api = True
        document.doc_updated_at = now
        document.semantic_identifier = document.semantic_identifier or file_name
        document.title = document.title or document.semantic_identifier
        document.doc_metadata = {
            **(document.doc_metadata or {}),
            "taxonomy_article_import": True,
            "taxonomy_article_file_id": file_id,
            "taxonomy_article_file_name": file_name,
            "taxonomy_article_imported_by": (
                str(created_by_user_id) if created_by_user_id else None
            ),
        }
        imported_documents.append(document)

    return imported_documents


def _created_by_uuid(created_by_user_id: str | UUID | None) -> UUID | None:
    if created_by_user_id is None:
        return None
    if isinstance(created_by_user_id, UUID):
        return created_by_user_id
    return UUID(str(created_by_user_id))


def process_taxonomy_article_import_files(
    *,
    files: list[TaxonomyArticleImportFile],
    db_session: Session,
    created_by_user_id: str | UUID | None,
) -> list[str]:
    user_id = _created_by_uuid(created_by_user_id)
    imported_documents: list[Document] = []

    for file in files:
        try:
            documents = load_taxonomy_article_documents_from_file_store(
                file_id=file.file_id,
                file_name=file.file_name,
            )
            if not documents:
                raise ValueError("文件未解析出可导入内容")

            imported_documents.extend(
                prepare_taxonomy_article_documents(
                    file_id=file.file_id,
                    file_name=file.file_name,
                    documents=documents,
                    created_by_user_id=user_id,
                )
            )
        except Exception:
            logger.exception("Failed to parse taxonomy article file %s", file.file_name)

    if not imported_documents:
        raise ValueError("未解析出可导入文章")

    indexing_result = index_ingestion_documents(
        documents=imported_documents,
        db_session=db_session,
    )
    if indexing_result is None:
        raise RuntimeError("No taxonomy article documents were indexed")

    failed_document_ids = {
        failure.failed_document.document_id
        for failure in indexing_result.failures
        if failure.failed_document is not None
    }
    imported_document_ids = [
        document.id
        for document in imported_documents
        if document.id not in failed_document_ids
    ]
    if not imported_document_ids:
        raise RuntimeError("All taxonomy article documents failed indexing")

    missing_summary_document_ids = get_document_ids_missing_complete_summary(
        db_session,
        document_ids=imported_document_ids,
    )
    for document_id in missing_summary_document_ids:
        upsert_document_summary(
            db_session,
            document_id=document_id,
            summary=None,
            status=TaxonomySummaryStatus.PENDING,
            is_manual=False,
        )
    db_session.commit()

    if missing_summary_document_ids:
        generate_summaries_for_documents(
            db_session=db_session,
            document_ids=missing_summary_document_ids,
            limit=len(missing_summary_document_ids),
            overwrite_manual=False,
            created_by_user_id=user_id,
        )

    return imported_document_ids
