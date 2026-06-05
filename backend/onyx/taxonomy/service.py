from __future__ import annotations

from datetime import datetime
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.db.enums import TaxonomyAssignmentStatus
from onyx.db.enums import TaxonomyCandidateStatus
from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.enums import TaxonomyNodeStatus
from onyx.db.enums import TaxonomyReviewStatus
from onyx.db.enums import TaxonomySummaryStatus
from onyx.db.enums import TaxonomyTaggingSource
from onyx.db.enums import TaxonomyTaggingTaskStatus
from onyx.db.enums import TaxonomyTagSource
from onyx.db.models import Document
from onyx.db.models import DocumentTaxonomyTag
from onyx.db.models import TaxonomyCandidateLabel
from onyx.db.models import TaxonomyNode
from onyx.db.models import TaxonomyTaggingTask
from onyx.db.taxonomy import get_active_taxonomy_version
from onyx.db.taxonomy import invalidate_active_document_taxonomy_tags
from onyx.db.taxonomy import project_taxonomy_tags_to_document_metadata
from onyx.db.taxonomy import upsert_document_summary
from onyx.llm.factory import get_default_llm
from onyx.llm.interfaces import LLM
from onyx.taxonomy.constants import TAXONOMY_PROMPT_VERSION
from onyx.taxonomy.llm_service import generate_document_summary
from onyx.taxonomy.llm_service import model_info
from onyx.taxonomy.llm_service import recommend_taxonomy_tags
from onyx.taxonomy.models import StartTaggingRequest
from onyx.utils.logger import setup_logger

logger = setup_logger()


def run_summary_tagging_if_possible(
    *,
    db_session: Session,
    document_ids: list[str],
    created_by_user_id,
) -> TaxonomyTaggingTask | None:
    if not document_ids:
        return None

    try:
        return run_tagging_task(
            db_session=db_session,
            request=StartTaggingRequest(
                document_ids=document_ids,
                source=TaxonomyTaggingSource.SUMMARY,
                enable_optimization=False,
                limit=len(document_ids),
            ),
            created_by_user_id=created_by_user_id,
        )
    except ValueError as e:
        db_session.rollback()
        logger.info("Skipped automatic taxonomy tagging after summary update: %s", e)
        return None
    except Exception as e:
        db_session.rollback()
        logger.exception("Failed automatic taxonomy tagging after summary update: %s", e)
        return None


def _document_content_from_index(
    *,
    document: Document,
    db_session: Session,
    max_chars: int = 12000,
) -> str:
    from onyx.context.search.models import IndexFilters
    from onyx.db.search_settings import get_current_search_settings
    from onyx.document_index.factory import get_default_document_index
    from onyx.document_index.interfaces_new import DocumentSectionRequest

    search_settings = get_current_search_settings(db_session)
    document_index = get_default_document_index(search_settings, None, db_session)
    chunks = document_index.id_based_retrieval(
        chunk_requests=[DocumentSectionRequest(document_id=document.id)],
        filters=IndexFilters(access_control_list=None),
        batch_retrieval=True,
    )
    content = "\n".join(chunk.content for chunk in chunks if chunk.content)
    return content[:max_chars]


def generate_summaries_for_documents(
    *,
    db_session: Session,
    document_ids: list[str],
    limit: int,
    overwrite_manual: bool,
    created_by_user_id,
) -> int:
    llm = get_default_llm(temperature=0)
    query = select(Document).order_by(Document.last_modified.desc()).limit(limit)
    if document_ids:
        query = select(Document).where(Document.id.in_(document_ids)).limit(limit)
    documents = list(db_session.scalars(query).all())
    processed = 0
    summarized_document_ids: list[str] = []
    for document in documents:
        existing = document.taxonomy_summary
        if existing and existing.is_manual and not overwrite_manual:
            continue
        try:
            content = _document_content_from_index(document=document, db_session=db_session)
            summary = generate_document_summary(
                document_title=document.semantic_id,
                document_content=content,
                llm=llm,
            )
            upsert_document_summary(
                db_session,
                document_id=document.id,
                summary=summary,
                status=TaxonomySummaryStatus.COMPLETE,
                is_manual=False,
                model_info=model_info(llm),
            )
            processed += 1
            summarized_document_ids.append(document.id)
        except Exception as e:
            logger.exception("Failed to generate taxonomy summary for %s", document.id)
            upsert_document_summary(
                db_session,
                document_id=document.id,
                summary=None,
                status=TaxonomySummaryStatus.FAILED,
                is_manual=False,
                failure_reason=str(e),
                model_info=model_info(llm),
            )
    db_session.commit()
    run_summary_tagging_if_possible(
        db_session=db_session,
        document_ids=summarized_document_ids,
        created_by_user_id=created_by_user_id,
    )
    return processed


def update_manual_summary(
    *,
    db_session: Session,
    document_id: str,
    summary: str,
    created_by_user_id,
) -> None:
    document = db_session.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found")
    upsert_document_summary(
        db_session,
        document_id=document_id,
        summary=summary,
        status=TaxonomySummaryStatus.COMPLETE,
        is_manual=True,
    )
    db_session.commit()
    run_summary_tagging_if_possible(
        db_session=db_session,
        document_ids=[document_id],
        created_by_user_id=created_by_user_id,
    )


def _get_documents_for_tagging(
    db_session: Session,
    *,
    document_ids: list[str],
    limit: int,
) -> list[Document]:
    query = select(Document).order_by(Document.last_modified.desc()).limit(limit)
    if document_ids:
        query = select(Document).where(Document.id.in_(document_ids)).limit(limit)
    return list(db_session.scalars(query).all())


def _active_leaf_nodes(db_session: Session, version_id: int) -> list[TaxonomyNode]:
    return list(
        db_session.scalars(
            select(TaxonomyNode).where(
                TaxonomyNode.version_id == version_id,
                TaxonomyNode.level == TaxonomyNodeLevel.LEAF,
                TaxonomyNode.status == TaxonomyNodeStatus.ACTIVE,
            )
        ).all()
    )


def _tagging_content(
    *,
    document: Document,
    db_session: Session,
    source,
) -> str:
    if source.value == "summary":
        summary = document.taxonomy_summary
        if summary and summary.summary and summary.status == TaxonomySummaryStatus.COMPLETE:
            return summary.summary
    return _document_content_from_index(document=document, db_session=db_session)


def run_tagging_task(
    *,
    db_session: Session,
    request: StartTaggingRequest,
    created_by_user_id,
) -> TaxonomyTaggingTask:
    version = get_active_taxonomy_version(db_session)
    if version is None:
        raise ValueError("No active taxonomy version")

    documents = _get_documents_for_tagging(
        db_session,
        document_ids=request.document_ids,
        limit=request.limit,
    )
    task = TaxonomyTaggingTask(
        version_id=version.id,
        status=TaxonomyTaggingTaskStatus.RUNNING,
        source=request.source,
        enable_optimization=request.enable_optimization,
        optimization_strength=request.optimization_strength,
        total_docs=len(documents),
        processed_docs=0,
        failed_docs=0,
        created_by_user_id=created_by_user_id,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.flush()

    llm: LLM = get_default_llm(temperature=0)
    leaf_nodes = _active_leaf_nodes(db_session, version.id)
    leaf_by_id = {node.id: node for node in leaf_nodes}

    for document in documents:
        try:
            content = _tagging_content(
                document=document,
                db_session=db_session,
                source=request.source,
            )
            result = recommend_taxonomy_tags(
                document_title=document.semantic_id,
                document_content=content,
                leaf_nodes=leaf_nodes,
                enable_optimization=request.enable_optimization,
                llm=llm,
            )
            invalidate_active_document_taxonomy_tags(
                db_session,
                document_id=document.id,
                reason=f"Retagged by taxonomy task {task.id}",
            )
            for index, recommendation in enumerate(result.tags):
                leaf_node = leaf_by_id.get(recommendation.leaf_node_id)
                if leaf_node is None:
                    continue
                db_session.add(
                    DocumentTaxonomyTag(
                        document_id=document.id,
                        leaf_node_id=leaf_node.id,
                        version_id=version.id,
                        task_id=task.id,
                        full_path_snapshot=leaf_node.full_path,
                        confidence=recommendation.confidence,
                        source=TaxonomyTagSource.AI_RECOMMENDED,
                        is_primary=index == 0,
                        sort_order=index,
                        evidence=recommendation.evidence,
                        unmatched_reason=result.unmatched_reason,
                        tagging_source_content=content,
                        prompt_version=TAXONOMY_PROMPT_VERSION,
                        model_info=model_info(llm),
                        review_status=TaxonomyReviewStatus.UNCONFIRMED,
                        status=(
                            TaxonomyAssignmentStatus.ACTIVE
                            if recommendation.confidence >= 0.5
                            else TaxonomyAssignmentStatus.NEEDS_REVIEW
                        ),
                    )
                )

            for candidate in result.candidates:
                status = TaxonomyCandidateStatus.NEEDS_HANDLING
                if candidate.redundancy_result == "reuse_existing":
                    status = TaxonomyCandidateStatus.REUSED_EXISTING
                elif candidate.redundancy_result == "not_redundant":
                    status = TaxonomyCandidateStatus.PENDING_REVIEW
                db_session.add(
                    TaxonomyCandidateLabel(
                        task_id=task.id,
                        document_id=document.id,
                        candidate_path=candidate.path,
                        definition=candidate.definition,
                        evidence=candidate.evidence,
                        confidence=candidate.confidence,
                        status=status,
                        redundancy_result=candidate.redundancy_result,
                        suggested_reuse_node_id=candidate.suggested_reuse_node_id,
                    )
                )

            project_taxonomy_tags_to_document_metadata(
                db_session,
                document_id=document.id,
            )
            task.processed_docs += 1
        except Exception as e:
            logger.exception("Failed to taxonomy-tag document %s", document.id)
            task.failed_docs += 1
            task.error_message = str(e)

    task.completed_at = datetime.now(timezone.utc)
    task.status = (
        TaxonomyTaggingTaskStatus.COMPLETE
        if task.failed_docs == 0
        else TaxonomyTaggingTaskStatus.COMPLETED_WITH_ERRORS
    )
    db_session.commit()
    return task
