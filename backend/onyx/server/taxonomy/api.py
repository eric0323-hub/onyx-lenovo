import json
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.auth.permissions import require_permission
from onyx.auth.users import current_curator_or_admin_user
from onyx.configs.constants import DocumentSource
from onyx.configs.constants import FileOrigin
from onyx.connectors.file.connector import LocalFileConnector
from onyx.connectors.models import Document
from onyx.connectors.models import HierarchyNode
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import Permission
from onyx.db.enums import TaxonomyAssignmentStatus
from onyx.db.enums import TaxonomyVersionSource
from onyx.db.models import DocumentTaxonomyTag
from onyx.db.models import Taxonomy
from onyx.db.models import TaxonomyTaggingTask
from onyx.db.taxonomy import activate_taxonomy_version
from onyx.db.taxonomy import create_taxonomy_version_from_tree
from onyx.db.taxonomy import document_taxonomy_tag_snapshot
from onyx.db.taxonomy import get_active_taxonomy
from onyx.db.taxonomy import get_document_ids_missing_complete_summary
from onyx.db.taxonomy import get_document_summaries
from onyx.db.taxonomy import get_taxonomy_coverage
from onyx.db.taxonomy import taxonomy_snapshot
from onyx.db.taxonomy import taxonomy_version_snapshot
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.file_processing.extract_file_text import get_file_ext
from onyx.file_store.file_store import get_default_file_store
from onyx.server.onyx_api.ingestion_service import index_ingestion_documents
from onyx.server.settings.store import load_settings
from onyx.server.utils_vector_db import require_vector_db
from onyx.taxonomy.default_template import get_default_taxonomy_template
from onyx.taxonomy.llm_service import generate_taxonomy_draft
from onyx.taxonomy.llm_service import generate_taxonomy_draft_events
from onyx.taxonomy.models import ArticleImportItem
from onyx.taxonomy.models import ArticleImportResponse
from onyx.taxonomy.models import CreateDraftRequest
from onyx.taxonomy.models import DefaultTemplateResponse
from onyx.taxonomy.models import DocumentTaxonomyTagSnapshot
from onyx.taxonomy.models import GenerateSummaryRequest
from onyx.taxonomy.models import GenerateTaxonomyDraftRequest
from onyx.taxonomy.models import MatchTaxonomyQueryRequest
from onyx.taxonomy.models import StartTaggingRequest
from onyx.taxonomy.models import TaxonomyDashboardResponse
from onyx.taxonomy.models import TaxonomyTaggingTaskSnapshot
from onyx.taxonomy.models import UpdateSummaryRequest
from onyx.taxonomy.search_matcher import match_taxonomy_query
from onyx.taxonomy.service import generate_summaries_for_documents
from onyx.taxonomy.service import run_tagging_task
from onyx.taxonomy.service import update_manual_summary

router = APIRouter(prefix="/admin/taxonomy")

SUPPORTED_ARTICLE_IMPORT_EXTENSIONS = {".md", ".markdown", ".pdf"}


def _safe_upload_filename(upload: UploadFile) -> str | None:
    if not upload.filename:
        return None
    return Path(upload.filename).name


def _validate_article_upload(upload: UploadFile) -> str:
    file_name = _safe_upload_filename(upload)
    if not file_name:
        raise ValueError("文件名不能为空")

    extension = get_file_ext(file_name)
    if extension not in SUPPORTED_ARTICLE_IMPORT_EXTENSIONS:
        raise ValueError("仅支持 Markdown 和 PDF 文件")

    return file_name


def _load_article_documents_from_file_store(
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


@router.get("/dashboard")
def get_taxonomy_dashboard(
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaxonomyDashboardResponse:
    taxonomy = get_active_taxonomy(db_session)
    recent_tasks = list(
        db_session.scalars(
            select(TaxonomyTaggingTask)
            .order_by(TaxonomyTaggingTask.created_at.desc())
            .limit(10)
        ).all()
    )
    return TaxonomyDashboardResponse(
        taxonomy=taxonomy_snapshot(taxonomy),
        coverage=get_taxonomy_coverage(db_session),
        summaries=get_document_summaries(db_session, limit=20),
        recent_tasks=[
            TaxonomyTaggingTaskSnapshot(
                id=task.id,
                version_id=task.version_id,
                status=task.status,
                source=task.source,
                enable_optimization=task.enable_optimization,
                optimization_strength=task.optimization_strength,
                total_docs=task.total_docs,
                processed_docs=task.processed_docs,
                failed_docs=task.failed_docs,
                error_message=task.error_message,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                updated_at=task.updated_at,
            )
            for task in recent_tasks
        ],
    )


@router.get("/default-template")
def get_default_template(
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> DefaultTemplateResponse:
    return DefaultTemplateResponse(nodes=get_default_taxonomy_template())


@router.post("/generate-draft")
def generate_draft(
    request: GenerateTaxonomyDraftRequest,
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> DefaultTemplateResponse:
    try:
        nodes = generate_taxonomy_draft(
            company_description=request.company_description,
            organization_context=request.organization_context,
            knowledge_scope=request.knowledge_scope,
            classification_preferences=request.classification_preferences,
            max_leaf_nodes=request.max_leaf_nodes,
        )
    except Exception as e:
        raise OnyxError(OnyxErrorCode.INTERNAL_ERROR, str(e)) from e
    return DefaultTemplateResponse(nodes=nodes)


@router.post("/generate-draft/stream")
def generate_draft_stream(
    request: GenerateTaxonomyDraftRequest,
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> StreamingResponse:
    def event_generator() -> Iterator[str]:
        try:
            for event in generate_taxonomy_draft_events(
                company_description=request.company_description,
                organization_context=request.organization_context,
                knowledge_scope=request.knowledge_scope,
                classification_preferences=request.classification_preferences,
                max_leaf_nodes=request.max_leaf_nodes,
                parallelism=request.parallelism,
            ):
                yield f"data: {event.model_dump_json()}\n\n"
        except Exception as e:
            payload = json.dumps(
                {
                    "type": "error",
                    "message": str(e),
                },
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/draft")
def create_draft(
    request: CreateDraftRequest,
    user=Depends(current_curator_or_admin_user),
    db_session: Session = Depends(get_session),
):
    try:
        version = create_taxonomy_version_from_tree(
            db_session,
            nodes=request.generated_nodes,
            selected_default_leaf_ids=request.selected_default_leaf_ids,
            taxonomy_name=request.name,
            industry_context=None,
            company_description=request.company_description,
            source=TaxonomyVersionSource.MANUAL,
            change_summary="Created taxonomy draft",
            change_reason=request.change_reason,
            created_by_user_id=user.id,
            activate=False,
        )
        db_session.commit()
        db_session.refresh(version)
        return taxonomy_version_snapshot(version)
    except ValueError as e:
        db_session.rollback()
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, str(e)) from e


@router.post("/version/{version_id}/activate")
def activate_version(
    version_id: int,
    user=Depends(current_curator_or_admin_user),
    db_session: Session = Depends(get_session),
):
    try:
        version = activate_taxonomy_version(
            db_session,
            version_id=version_id,
            user_id=user.id,
        )
        db_session.commit()
        db_session.refresh(version)
        return taxonomy_version_snapshot(version)
    except ValueError as e:
        db_session.rollback()
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, str(e)) from e


@router.get("/versions")
def list_versions(
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
):
    taxonomy = db_session.scalar(select(Taxonomy).order_by(Taxonomy.id.asc()).limit(1))
    if taxonomy is None:
        return []
    return [
        taxonomy_version_snapshot(version)
        for version in sorted(
            taxonomy.versions,
            key=lambda version: version.version_number,
            reverse=True,
        )
    ]


@router.post("/summaries/generate")
def generate_summaries(
    request: GenerateSummaryRequest,
    user=Depends(current_curator_or_admin_user),
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> dict[str, int]:
    try:
        count = generate_summaries_for_documents(
            db_session=db_session,
            document_ids=request.document_ids,
            limit=request.limit,
            overwrite_manual=request.overwrite_manual,
            created_by_user_id=user.id,
        )
        return {"processed": count}
    except Exception as e:
        db_session.rollback()
        raise OnyxError(OnyxErrorCode.INTERNAL_ERROR, str(e)) from e


@router.post("/articles/import", dependencies=[Depends(require_vector_db)])
def import_articles(
    files: list[UploadFile] = File(...),
    user=Depends(current_curator_or_admin_user),
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ArticleImportResponse:
    if not files:
        raise OnyxError(OnyxErrorCode.MISSING_REQUIRED_FIELD, "请选择要导入的文件")

    file_store = get_default_file_store()
    imported: list[ArticleImportItem] = []
    failed: list[ArticleImportItem] = []

    for upload in files:
        display_name = _safe_upload_filename(upload) or "未命名文件"
        try:
            file_name = _validate_article_upload(upload)
            file_id = file_store.save_file(
                content=upload.file,
                display_name=file_name,
                file_origin=FileOrigin.CONNECTOR_FILE_UPLOAD,
                file_type=upload.content_type or "application/octet-stream",
            )
            documents = _load_article_documents_from_file_store(
                file_id=file_id,
                file_name=file_name,
            )
            if not documents:
                raise ValueError("文件未解析出可导入内容")

            imported_documents: list[Document] = []
            for index, document in enumerate(documents):
                document.id = (
                    f"taxonomy_article__{file_id}"
                    if index == 0
                    else f"taxonomy_article__{file_id}__{index}"
                )
                document.source = DocumentSource.FILE
                document.from_ingestion_api = True
                document.doc_updated_at = datetime.now(timezone.utc)
                document.semantic_identifier = document.semantic_identifier or file_name
                document.title = document.title or document.semantic_identifier
                document.doc_metadata = {
                    **(document.doc_metadata or {}),
                    "taxonomy_article_import": True,
                    "taxonomy_article_file_id": file_id,
                    "taxonomy_article_file_name": file_name,
                    "taxonomy_article_imported_by": str(user.id) if user.id else None,
                }
                imported_documents.append(document)

            index_ingestion_documents(
                documents=imported_documents,
                db_session=db_session,
            )
            imported_document_ids = [document.id for document in imported_documents]
            missing_summary_document_ids = get_document_ids_missing_complete_summary(
                db_session,
                document_ids=imported_document_ids,
            )
            if missing_summary_document_ids:
                generate_summaries_for_documents(
                    db_session=db_session,
                    document_ids=missing_summary_document_ids,
                    limit=len(missing_summary_document_ids),
                    overwrite_manual=False,
                    created_by_user_id=user.id,
                )
            imported.extend(
                ArticleImportItem(
                    file_name=file_name,
                    document_id=document.id,
                    status="imported",
                    detail="已导入并进入解析打标链路",
                )
                for document in imported_documents
            )
        except OnyxError:
            db_session.rollback()
            raise
        except Exception as e:
            db_session.rollback()
            failed.append(
                ArticleImportItem(
                    file_name=display_name,
                    status="failed",
                    detail=str(e),
                )
            )

    if not imported and failed:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            failed[0].detail or "文章导入失败",
        )

    return ArticleImportResponse(imported=imported, failed=failed)


@router.put("/summaries/{document_id}")
def update_summary(
    document_id: str,
    request: UpdateSummaryRequest,
    user=Depends(current_curator_or_admin_user),
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> dict[str, str]:
    try:
        update_manual_summary(
            db_session=db_session,
            document_id=document_id,
            summary=request.summary,
            created_by_user_id=user.id,
        )
        return {"status": "ok"}
    except ValueError as e:
        db_session.rollback()
        raise OnyxError(OnyxErrorCode.NOT_FOUND, str(e)) from e


@router.post("/tagging/run")
def run_tagging(
    request: StartTaggingRequest,
    user=Depends(current_curator_or_admin_user),
    db_session: Session = Depends(get_session),
) -> TaxonomyTaggingTaskSnapshot:
    try:
        task = run_tagging_task(
            db_session=db_session,
            request=request,
            created_by_user_id=user.id,
        )
        return TaxonomyTaggingTaskSnapshot(
            id=task.id,
            version_id=task.version_id,
            status=task.status,
            source=task.source,
            enable_optimization=task.enable_optimization,
            optimization_strength=task.optimization_strength,
            total_docs=task.total_docs,
            processed_docs=task.processed_docs,
            failed_docs=task.failed_docs,
            error_message=task.error_message,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            updated_at=task.updated_at,
        )
    except ValueError as e:
        db_session.rollback()
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, str(e)) from e
    except Exception as e:
        db_session.rollback()
        raise OnyxError(OnyxErrorCode.INTERNAL_ERROR, str(e)) from e


@router.get("/documents/{document_id}/tags")
def get_document_tags(
    document_id: str,
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[DocumentTaxonomyTagSnapshot]:
    tags = list(
        db_session.scalars(
            select(DocumentTaxonomyTag)
            .where(
                DocumentTaxonomyTag.document_id == document_id,
                DocumentTaxonomyTag.status != TaxonomyAssignmentStatus.STALE,
            )
            .order_by(DocumentTaxonomyTag.created_at.desc())
        ).all()
    )
    return [document_taxonomy_tag_snapshot(tag) for tag in tags]


@router.post("/match-query")
def match_query(
    request: MatchTaxonomyQueryRequest,
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
):
    return match_taxonomy_query(
        query=request.query,
        settings=load_settings(),
        apply_to=request.apply_to,
        db_session=db_session,
        manual_node_ids=request.manual_node_ids,
    )
