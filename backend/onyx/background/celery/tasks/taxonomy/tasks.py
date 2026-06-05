from celery import shared_task
from celery import Task

from onyx.background.celery.apps.app_base import task_logger
from onyx.configs.constants import OnyxCeleryTask
from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.taxonomy.article_import import process_taxonomy_article_import_files
from onyx.taxonomy.article_import import TaxonomyArticleImportFile


@shared_task(
    name=OnyxCeleryTask.PROCESS_TAXONOMY_ARTICLE_IMPORT,
    ignore_result=True,
    bind=True,
)
def process_taxonomy_article_import_task(
    self: Task,
    *,
    files: list[dict[str, str]],
    created_by_user_id: str | None,
    tenant_id: str,
) -> None:
    _ = self
    article_files = [
        TaxonomyArticleImportFile.model_validate(file_payload) for file_payload in files
    ]
    if not article_files:
        task_logger.info("No taxonomy article files supplied for tenant=%s", tenant_id)
        return

    task_logger.info(
        "Starting taxonomy article import for tenant=%s files=%s",
        tenant_id,
        [file.file_name for file in article_files],
    )
    with get_session_with_current_tenant() as db_session:
        document_ids = process_taxonomy_article_import_files(
            files=article_files,
            db_session=db_session,
            created_by_user_id=created_by_user_id,
        )

    task_logger.info(
        "Finished taxonomy article import for tenant=%s documents=%s",
        tenant_id,
        document_ids,
    )
