import json
from collections.abc import Iterator

from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.auth.permissions import require_permission
from onyx.auth.users import current_curator_or_admin_user
from onyx.background.celery.versioned_apps.client import app as client_app
from onyx.configs.constants import CELERY_TAXONOMY_ARTICLE_IMPORT_TASK_EXPIRES
from onyx.configs.constants import FileOrigin
from onyx.configs.constants import OnyxCeleryPriority
from onyx.configs.constants import OnyxCeleryQueues
from onyx.configs.constants import OnyxCeleryTask
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
from onyx.db.taxonomy import get_document_summaries
from onyx.db.taxonomy import get_taxonomy_coverage
from onyx.db.taxonomy import taxonomy_snapshot
from onyx.db.taxonomy import taxonomy_version_snapshot
from onyx.db.taxonomy_generation_config import get_taxonomy_generation_config
from onyx.db.taxonomy_generation_config import set_taxonomy_generation_config
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.file_store.file_store import get_default_file_store
from onyx.server.settings.store import load_settings
from onyx.server.utils_vector_db import require_vector_db
from onyx.taxonomy.article_import import safe_taxonomy_article_file_name
from onyx.taxonomy.article_import import validate_taxonomy_article_file_name
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
from onyx.taxonomy.models import TaxonomyGenerationConfig
from onyx.taxonomy.models import TaxonomyGenerationRuntimeConfig
from onyx.taxonomy.models import TaxonomyTaggingTaskSnapshot
from onyx.taxonomy.models import UpdateSummaryRequest
from onyx.taxonomy.search_matcher import match_taxonomy_query
from onyx.taxonomy.service import generate_summaries_for_documents
from onyx.taxonomy.service import run_tagging_task
from onyx.taxonomy.service import update_manual_summary
from shared_configs.contextvars import get_current_tenant_id

router = APIRouter(prefix="/admin/taxonomy")


def _runtime_generation_config_from_template_config(
    generation_config: TaxonomyGenerationConfig,
) -> TaxonomyGenerationRuntimeConfig:
    return TaxonomyGenerationRuntimeConfig(
        first_level_candidate_multiplier=(
            generation_config.first_level_candidate_multiplier
        ),
        first_level_max_count=generation_config.first_level_max_count,
        third_level_candidate_multiplier=(
            generation_config.third_level_candidate_multiplier
        ),
        third_level_max_count=generation_config.third_level_max_count,
        third_level_parallelism=generation_config.third_level_parallelism,
        l1_l2_system_prompt=generation_config.l1_l2_prompt_template,
        leaf_system_prompt=generation_config.leaf_prompt_template,
    )


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


@router.get("/generation-config")
def get_generation_config(
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> TaxonomyGenerationConfig:
    return get_taxonomy_generation_config()


@router.put("/generation-config")
def update_generation_config(
    request: TaxonomyGenerationConfig,
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> TaxonomyGenerationConfig:
    try:
        return set_taxonomy_generation_config(request)
    except ValueError as e:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, str(e)) from e


@router.post("/generate-draft")
def generate_draft(
    request: GenerateTaxonomyDraftRequest,
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> DefaultTemplateResponse:
    generation_config = request.generation_config or (
        _runtime_generation_config_from_template_config(
            get_taxonomy_generation_config()
        )
    )
    try:
        nodes = generate_taxonomy_draft(
            company_description=request.company_description,
            organization_context=request.organization_context,
            knowledge_scope=request.knowledge_scope,
            classification_preferences=request.classification_preferences,
            max_leaf_nodes=request.max_leaf_nodes,
            generation_config=generation_config,
        )
    except Exception as e:
        raise OnyxError(OnyxErrorCode.INTERNAL_ERROR, str(e)) from e
    return DefaultTemplateResponse(nodes=nodes)


@router.post("/generate-draft/stream")
def generate_draft_stream(
    request: GenerateTaxonomyDraftRequest,
    _: object = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> StreamingResponse:
    generation_config = request.generation_config or (
        _runtime_generation_config_from_template_config(
            get_taxonomy_generation_config()
        )
    )

    def event_generator() -> Iterator[str]:
        try:
            for event in generate_taxonomy_draft_events(
                company_description=request.company_description,
                organization_context=request.organization_context,
                knowledge_scope=request.knowledge_scope,
                classification_preferences=request.classification_preferences,
                max_leaf_nodes=request.max_leaf_nodes,
                parallelism=request.parallelism,
                generation_config=generation_config,
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
) -> ArticleImportResponse:
    if not files:
        raise OnyxError(OnyxErrorCode.MISSING_REQUIRED_FIELD, "请选择要导入的文件")

    file_store = get_default_file_store()
    queued: list[ArticleImportItem] = []
    failed: list[ArticleImportItem] = []
    task_files: list[dict[str, str]] = []

    for upload in files:
        display_name = safe_taxonomy_article_file_name(upload.filename) or "未命名文件"
        try:
            file_name = validate_taxonomy_article_file_name(upload.filename)
            file_id = file_store.save_file(
                content=upload.file,
                display_name=file_name,
                file_origin=FileOrigin.CONNECTOR_FILE_UPLOAD,
                file_type=upload.content_type or "application/octet-stream",
            )
            task_files.append({"file_id": file_id, "file_name": file_name})
            queued.append(
                ArticleImportItem(
                    file_name=file_name,
                    status="queued",
                    detail="已上传，后台处理中",
                )
            )
        except Exception as e:
            failed.append(
                ArticleImportItem(
                    file_name=display_name,
                    status="failed",
                    detail=str(e),
                )
            )

    if not queued and failed:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            failed[0].detail or "文章导入失败",
        )

    if task_files:
        try:
            client_app.send_task(
                OnyxCeleryTask.PROCESS_TAXONOMY_ARTICLE_IMPORT,
                kwargs={
                    "files": task_files,
                    "created_by_user_id": str(user.id) if user.id else None,
                    "tenant_id": get_current_tenant_id(),
                },
                queue=OnyxCeleryQueues.TAXONOMY_PROCESSING,
                priority=OnyxCeleryPriority.HIGH,
                expires=CELERY_TAXONOMY_ARTICLE_IMPORT_TASK_EXPIRES,
            )
        except Exception as e:
            raise OnyxError(
                OnyxErrorCode.INTERNAL_ERROR,
                f"文章已上传但后台任务启动失败: {e}",
            ) from e

    return ArticleImportResponse(imported=queued, failed=failed)


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
