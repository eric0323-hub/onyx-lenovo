from __future__ import annotations

import re
from datetime import datetime
from datetime import timezone
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from onyx.configs.app_configs import TAXONOMY_AUTO_TAGGING_ENABLE_OPTIMIZATION
from onyx.configs.app_configs import TAXONOMY_TAG_CONFIDENCE_ACTIVE_THRESHOLD
from onyx.db.enums import TaxonomyAssignmentStatus
from onyx.db.enums import TaxonomyCandidateStatus
from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.enums import TaxonomyNodeSource
from onyx.db.enums import TaxonomyNodeStatus
from onyx.db.enums import TaxonomyReviewStatus
from onyx.db.enums import TaxonomySummaryStatus
from onyx.db.enums import TaxonomyTaggingSource
from onyx.db.enums import TaxonomyTaggingTaskStatus
from onyx.db.enums import TaxonomyTagSource
from onyx.db.enums import TaxonomyVersionSource
from onyx.db.models import Document
from onyx.db.models import DocumentTaxonomyTag
from onyx.db.models import TaxonomyCandidateLabel
from onyx.db.models import TaxonomyNode
from onyx.db.models import TaxonomyTaggingTask
from onyx.db.models import TaxonomyVersion
from onyx.db.taxonomy import create_taxonomy_version_from_tree
from onyx.db.taxonomy import get_active_taxonomy_version
from onyx.db.taxonomy import invalidate_active_document_taxonomy_tags
from onyx.db.taxonomy import project_taxonomy_tags_to_document_metadata
from onyx.db.taxonomy import upsert_document_summary
from onyx.llm.factory import get_default_llm
from onyx.llm.interfaces import LLM
from onyx.taxonomy.constants import TAXONOMY_PROMPT_VERSION
from onyx.taxonomy.llm_service import generate_document_summary
from onyx.taxonomy.llm_service import model_info
from onyx.taxonomy.llm_service import recommend_existing_taxonomy_tags_forced
from onyx.taxonomy.llm_service import recommend_taxonomy_tags
from onyx.taxonomy.llm_service import review_taxonomy_candidate_labels
from onyx.taxonomy.llm_service import TaxonomyCandidateForHealthCheck
from onyx.taxonomy.llm_service import TaxonomyCandidateHealthDecision
from onyx.taxonomy.models import StartTaggingRequest
from onyx.taxonomy.models import TaxonomyNodeCreate
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
                enable_optimization=TAXONOMY_AUTO_TAGGING_ENABLE_OPTIMIZATION,
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


def _slugify_taxonomy_code(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", value.strip()).strip("_")
    return cleaned.lower() or uuid4().hex[:8]


def _taxonomy_version_tree(
    version: TaxonomyVersion,
) -> tuple[list[TaxonomyNodeCreate], dict[str, TaxonomyNodeCreate]]:
    nodes = sorted(version.nodes, key=lambda node: (node.sort_order, node.name))
    children_by_parent: dict[str | None, list[TaxonomyNode]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    node_by_old_id: dict[str, TaxonomyNodeCreate] = {}

    def build_node(node: TaxonomyNode) -> TaxonomyNodeCreate:
        stable_node_id = node.code or node.id
        created = TaxonomyNodeCreate(
            id=stable_node_id,
            parent_id=None,
            level=node.level,
            code=node.code,
            name=node.name,
            display_name=node.display_name,
            definition=node.definition,
            applicability=node.applicability,
            exclusion=node.exclusion,
            positive_examples=list(node.positive_examples or []),
            negative_examples=list(node.negative_examples or []),
            keywords=list(node.keywords or []),
            synonyms=list(node.synonyms or []),
            tagging_guidance=node.tagging_guidance,
            conflict_rules=node.conflict_rules,
            source=node.source,
            source_detail=node.source_detail,
            status=TaxonomyNodeStatus.DRAFT,
            sort_order=node.sort_order,
            children=[
                build_node(child) for child in children_by_parent.get(node.id, [])
            ],
        )
        node_by_old_id[node.id] = created
        return created

    return (
        [build_node(node) for node in children_by_parent.get(None, [])],
        node_by_old_id,
    )


def _active_nodes_by_level(
    db_session: Session,
    *,
    version_id: int,
    level: TaxonomyNodeLevel,
) -> list[TaxonomyNode]:
    return list(
        db_session.scalars(
            select(TaxonomyNode).where(
                TaxonomyNode.version_id == version_id,
                TaxonomyNode.level == level,
                TaxonomyNode.status == TaxonomyNodeStatus.ACTIVE,
            )
        ).all()
    )


def _task_leaf_code(*, task_id: int, candidate_id: int, name: str) -> str:
    return f"task_{task_id}_{candidate_id}_{_slugify_taxonomy_code(name)[:48]}"


def _append_task_leaf_node(
    *,
    task_id: int,
    decision: TaxonomyCandidateHealthDecision,
    parent_node: TaxonomyNodeCreate,
) -> TaxonomyNodeCreate:
    if decision.leaf_name is None:
        raise ValueError("Cannot append task leaf without a leaf name")
    code = _task_leaf_code(
        task_id=task_id,
        candidate_id=decision.candidate_id,
        name=decision.leaf_name,
    )
    leaf = TaxonomyNodeCreate(
        id=code,
        parent_id=parent_node.id,
        level=TaxonomyNodeLevel.LEAF,
        code=code,
        name=decision.leaf_name,
        definition=decision.definition or decision.leaf_name,
        applicability=decision.applicability or decision.definition or decision.leaf_name,
        positive_examples=decision.positive_examples or [decision.reason],
        negative_examples=decision.negative_examples or ["不属于该新增标签定义的文档"],
        keywords=decision.keywords or [decision.leaf_name],
        synonyms=decision.synonyms or [],
        tagging_guidance=decision.reason,
        source=TaxonomyNodeSource.TASK_GENERATED,
        source_detail=f"taxonomy_tagging_task:{task_id};candidate:{decision.candidate_id}",
        status=TaxonomyNodeStatus.DRAFT,
        sort_order=len(parent_node.children),
    )
    parent_node.children.append(leaf)
    return leaf


def _added_leaf_change_comment(leaf_names: list[str]) -> str:
    unique_leaf_names = list(dict.fromkeys(name for name in leaf_names if name))
    if not unique_leaf_names:
        return "新增标签"
    return f"新增标签：{'、'.join(unique_leaf_names)}"


def _active_tag_count_for_document(db_session: Session, *, document_id: str) -> int:
    return (
        db_session.scalar(
            select(func.count(DocumentTaxonomyTag.id)).where(
                DocumentTaxonomyTag.document_id == document_id,
                DocumentTaxonomyTag.status == TaxonomyAssignmentStatus.ACTIVE,
            )
        )
        or 0
    )


def _has_successful_taxonomy_tag(
    db_session: Session,
    *,
    document_id: str,
    task_id: int,
) -> bool:
    return (
        db_session.scalar(
            select(func.count(DocumentTaxonomyTag.id)).where(
                DocumentTaxonomyTag.document_id == document_id,
                DocumentTaxonomyTag.task_id == task_id,
                DocumentTaxonomyTag.status.in_(
                    [
                        TaxonomyAssignmentStatus.ACTIVE,
                        TaxonomyAssignmentStatus.NEEDS_REVIEW,
                    ]
                ),
            )
        )
        or 0
    ) > 0


def _add_task_generated_tag(
    *,
    db_session: Session,
    document_id: str,
    leaf_node: TaxonomyNode,
    version_id: int,
    task_id: int,
    confidence: float,
    evidence: str,
    reason: str,
    tagging_source_content: str,
) -> None:
    active_count = _active_tag_count_for_document(db_session, document_id=document_id)
    db_session.add(
        DocumentTaxonomyTag(
            document_id=document_id,
            leaf_node_id=leaf_node.id,
            version_id=version_id,
            task_id=task_id,
            full_path_snapshot=leaf_node.full_path,
            confidence=confidence,
            source=TaxonomyTagSource.TASK_GENERATED,
            is_primary=active_count == 0,
            sort_order=active_count,
            evidence=evidence,
            unmatched_reason=reason or None,
            tagging_source_content=tagging_source_content,
            prompt_version=TAXONOMY_PROMPT_VERSION,
            model_info=None,
            review_status=TaxonomyReviewStatus.UNCONFIRMED,
            status=TaxonomyAssignmentStatus.ACTIVE,
        )
    )


def _reuse_existing_leaf_for_candidate(
    *,
    db_session: Session,
    candidate: TaxonomyCandidateLabel,
    decision: TaxonomyCandidateHealthDecision,
    leaf_node: TaxonomyNode,
    task_id: int,
    document_content_by_id: dict[str, str],
) -> None:
    candidate.status = TaxonomyCandidateStatus.REUSED_EXISTING
    candidate.suggested_reuse_node_id = leaf_node.id
    _add_task_generated_tag(
        db_session=db_session,
        document_id=candidate.document_id,
        leaf_node=leaf_node,
        version_id=leaf_node.version_id,
        task_id=task_id,
        confidence=candidate.confidence,
        evidence=candidate.evidence,
        reason=decision.reason,
        tagging_source_content=document_content_by_id.get(
            candidate.document_id, candidate.evidence
        ),
    )


def _add_tagging_failed_marker(
    *,
    db_session: Session,
    document_id: str,
    version_id: int,
    task_id: int,
    failure_reason: str,
    tagging_source_content: str,
) -> None:
    db_session.add(
        DocumentTaxonomyTag(
            document_id=document_id,
            leaf_node_id=None,
            version_id=version_id,
            task_id=task_id,
            full_path_snapshot="打标签失败",
            confidence=0,
            source=TaxonomyTagSource.AI_RECOMMENDED,
            is_primary=False,
            sort_order=0,
            evidence=None,
            unmatched_reason=failure_reason,
            tagging_source_content=tagging_source_content,
            prompt_version=TAXONOMY_PROMPT_VERSION,
            model_info=None,
            review_status=TaxonomyReviewStatus.UNCONFIRMED,
            status=TaxonomyAssignmentStatus.TAGGING_FAILED,
        )
    )


def _add_existing_label_fallback_tags(
    *,
    db_session: Session,
    document: Document,
    content: str,
    leaf_nodes: list[TaxonomyNode],
    task: TaxonomyTaggingTask,
    llm: LLM,
) -> bool:
    result = recommend_existing_taxonomy_tags_forced(
        document_title=document.semantic_id,
        document_content=content,
        leaf_nodes=leaf_nodes,
        llm=llm,
    )
    leaf_by_id = {node.id: node for node in leaf_nodes}
    added_any = False
    seen_leaf_ids: set[str] = set()
    for index, recommendation in enumerate(result.tags):
        if recommendation.leaf_node_id in seen_leaf_ids:
            continue
        leaf_node = leaf_by_id.get(recommendation.leaf_node_id)
        if leaf_node is None:
            continue
        seen_leaf_ids.add(recommendation.leaf_node_id)
        db_session.add(
            DocumentTaxonomyTag(
                document_id=document.id,
                leaf_node_id=leaf_node.id,
                version_id=leaf_node.version_id,
                task_id=task.id,
                full_path_snapshot=leaf_node.full_path,
                confidence=recommendation.confidence,
                source=TaxonomyTagSource.AI_RECOMMENDED,
                is_primary=index == 0,
                sort_order=index,
                evidence=recommendation.evidence,
                unmatched_reason=result.reason or None,
                tagging_source_content=content,
                prompt_version=TAXONOMY_PROMPT_VERSION,
                model_info=model_info(llm),
                review_status=TaxonomyReviewStatus.UNCONFIRMED,
                status=TaxonomyAssignmentStatus.ACTIVE,
            )
        )
        added_any = True
    return added_any


def _candidate_health_inputs(
    candidates: list[TaxonomyCandidateLabel],
) -> list[TaxonomyCandidateForHealthCheck]:
    return [
        TaxonomyCandidateForHealthCheck(
            candidate_id=candidate.id,
            document_id=candidate.document_id,
            path=list(candidate.candidate_path),
            definition=candidate.definition,
            evidence=candidate.evidence,
            confidence=candidate.confidence,
        )
        for candidate in candidates
    ]


def _add_low_confidence_leaf_candidate(
    *,
    db_session: Session,
    task_id: int,
    document_id: str,
    leaf_node: TaxonomyNode,
    confidence: float,
    evidence: str,
    unmatched_reason: str | None,
) -> TaxonomyCandidateLabel:
    path = list(leaf_node.full_path.split(" / "))
    if len(path) != 3:
        path = (
            [*path[:2], leaf_node.name]
            if len(path) >= 2
            else ["待分类", "待分类", leaf_node.name]
        )
    candidate = TaxonomyCandidateLabel(
        task_id=task_id,
        document_id=document_id,
        candidate_path=path,
        definition=(
            f"基于低置信已有标签“{leaf_node.full_path}”提出的更贴切三级标签候选。"
            f"原标签置信度为 {confidence:.2f}，低于自动生效阈值 "
            f"{TAXONOMY_TAG_CONFIDENCE_ACTIVE_THRESHOLD:.2f}。"
        ),
        evidence=evidence
        or unmatched_reason
        or f"已有标签“{leaf_node.full_path}”置信度低于阈值，需要健康自检判断是否新增或复用。",
        confidence=max(confidence, TAXONOMY_TAG_CONFIDENCE_ACTIVE_THRESHOLD),
        status=TaxonomyCandidateStatus.PENDING_REVIEW,
        redundancy_result="pending_health_check",
        suggested_reuse_node_id=None,
    )
    db_session.add(candidate)
    return candidate


def _active_leaf_nodes_by_code(
    db_session: Session,
    *,
    version_id: int,
) -> dict[str, TaxonomyNode]:
    return {
        node.code: node
        for node in _active_nodes_by_level(
            db_session,
            version_id=version_id,
            level=TaxonomyNodeLevel.LEAF,
        )
        if node.code is not None
    }


def _remap_task_tags_to_version(
    *,
    db_session: Session,
    task_id: int,
    target_version: TaxonomyVersion,
) -> None:
    target_leaf_by_code = _active_leaf_nodes_by_code(
        db_session,
        version_id=target_version.id,
    )
    if not target_leaf_by_code:
        return

    task_tags = list(
        db_session.scalars(
            select(DocumentTaxonomyTag)
            .options(selectinload(DocumentTaxonomyTag.leaf_node))
            .where(
                DocumentTaxonomyTag.task_id == task_id,
                DocumentTaxonomyTag.leaf_node_id.is_not(None),
            )
        ).all()
    )
    for tag in task_tags:
        if tag.leaf_node is None or tag.leaf_node.code is None:
            continue
        target_leaf = target_leaf_by_code.get(tag.leaf_node.code)
        if target_leaf is None or target_leaf.id == tag.leaf_node_id:
            continue
        tag.leaf_node_id = target_leaf.id
        tag.leaf_node = target_leaf
        tag.version_id = target_version.id
        tag.full_path_snapshot = target_leaf.full_path


def _process_candidate_labels_after_batch(
    *,
    db_session: Session,
    task: TaxonomyTaggingTask,
    version: TaxonomyVersion,
    candidate_labels: list[TaxonomyCandidateLabel],
    document_content_by_id: dict[str, str],
    created_by_user_id,
    llm: LLM,
) -> None:
    db_session.flush()
    base_version = get_active_taxonomy_version(db_session) or version
    if not candidate_labels:
        if base_version.id != version.id:
            _remap_task_tags_to_version(
                db_session=db_session,
                task_id=task.id,
                target_version=base_version,
            )
        return

    leaf_nodes = _active_nodes_by_level(
        db_session,
        version_id=base_version.id,
        level=TaxonomyNodeLevel.LEAF,
    )
    l2_nodes = _active_nodes_by_level(
        db_session,
        version_id=base_version.id,
        level=TaxonomyNodeLevel.L2,
    )
    decisions = review_taxonomy_candidate_labels(
        candidates=_candidate_health_inputs(candidate_labels),
        leaf_nodes=leaf_nodes,
        l2_nodes=l2_nodes,
        optimization_strength=task.optimization_strength,
        llm=llm,
    )
    decision_by_candidate_id = {
        decision.candidate_id: decision for decision in decisions
    }
    reusable_leaf_by_id = {node.id: node for node in leaf_nodes}

    add_decisions = [
        decision
        for decision in decisions
        if decision.action == "add_leaf" and decision.parent_l2_node_id
    ]
    new_version: TaxonomyVersion | None = None
    new_leaf_by_candidate_id: dict[int, TaxonomyNode] = {}
    base_leaf_to_new_leaf: dict[str, TaxonomyNode] = {}

    if add_decisions:
        tree, node_by_old_id = _taxonomy_version_tree(base_version)
        added_codes_by_candidate_id: dict[int, str] = {}
        code_by_add_key: dict[tuple[str, str], str] = {}
        seen_add_keys: dict[tuple[str, str], str] = {}
        added_leaf_names_by_code: dict[str, str] = {}
        for decision in add_decisions:
            parent_node = node_by_old_id.get(decision.parent_l2_node_id or "")
            if parent_node is None:
                continue
            leaf_name = decision.leaf_name or ""
            add_key = (
                decision.parent_l2_node_id or "",
                _slugify_taxonomy_code(leaf_name),
            )
            if add_key in seen_add_keys:
                added_codes_by_candidate_id[decision.candidate_id] = seen_add_keys[
                    add_key
                ]
                code_by_add_key[add_key] = seen_add_keys[add_key]
                continue
            leaf = _append_task_leaf_node(
                task_id=task.id,
                decision=decision,
                parent_node=parent_node,
            )
            if leaf.code is None:
                continue
            added_leaf_names_by_code[leaf.code] = decision.leaf_name or leaf.name
            seen_add_keys[add_key] = leaf.code
            code_by_add_key[add_key] = leaf.code
            added_codes_by_candidate_id[decision.candidate_id] = leaf.code

        if added_codes_by_candidate_id:
            added_code_values = set(added_codes_by_candidate_id.values())
            added_leaf_comment = _added_leaf_change_comment(
                [
                    added_leaf_names_by_code[code]
                    for code in added_leaf_names_by_code
                    if code in added_code_values
                ]
            )
            new_version = create_taxonomy_version_from_tree(
                db_session,
                nodes=tree,
                taxonomy_name=None,
                industry_context=None,
                company_description=None,
                source=TaxonomyVersionSource.TAGGING_OPTIMIZATION,
                change_summary=added_leaf_comment,
                change_reason=added_leaf_comment,
                created_by_user_id=created_by_user_id,
                activate=True,
            )
            db_session.flush()
            new_nodes = list(
                db_session.scalars(
                    select(TaxonomyNode).where(
                        TaxonomyNode.version_id == new_version.id
                    )
                ).all()
            )
            new_leaf_by_code = {
                node.code: node
                for node in new_nodes
                if node.level == TaxonomyNodeLevel.LEAF and node.code is not None
            }
            old_leaf_by_code = {
                node.code: node
                for node in leaf_nodes
                if node.code is not None
            }
            for code, old_leaf in old_leaf_by_code.items():
                new_leaf = new_leaf_by_code.get(code)
                if new_leaf:
                    base_leaf_to_new_leaf[old_leaf.id] = new_leaf
            for candidate_id, code in added_codes_by_candidate_id.items():
                new_leaf = new_leaf_by_code.get(code)
                if new_leaf:
                    new_leaf_by_candidate_id[candidate_id] = new_leaf

            _remap_task_tags_to_version(
                db_session=db_session,
                task_id=task.id,
                target_version=new_version,
            )

            for candidate_id, decision in decision_by_candidate_id.items():
                if decision.action != "add_leaf" or not decision.parent_l2_node_id:
                    continue
                add_key = (
                    decision.parent_l2_node_id,
                    _slugify_taxonomy_code(decision.leaf_name or ""),
                )
                code = code_by_add_key.get(add_key)
                if code is None:
                    continue
                new_leaf = new_leaf_by_code.get(code)
                if new_leaf is not None:
                    new_leaf_by_candidate_id[candidate_id] = new_leaf
    elif base_version.id != version.id:
        _remap_task_tags_to_version(
            db_session=db_session,
            task_id=task.id,
            target_version=base_version,
        )

    for candidate in candidate_labels:
        decision = decision_by_candidate_id.get(candidate.id)
        if decision is None:
            candidate.status = TaxonomyCandidateStatus.NEEDS_HANDLING
            candidate.redundancy_result = "needs_handling"
            continue

        candidate.redundancy_result = decision.action
        if (
            decision.action in {"reuse_existing", "reject"}
            and decision.suggested_reuse_node_id
        ):
            leaf_node = reusable_leaf_by_id.get(decision.suggested_reuse_node_id)
            if leaf_node is None:
                candidate.status = TaxonomyCandidateStatus.NEEDS_HANDLING
                continue
            if new_version is not None:
                leaf_node = base_leaf_to_new_leaf.get(leaf_node.id, leaf_node)
            _reuse_existing_leaf_for_candidate(
                db_session=db_session,
                candidate=candidate,
                decision=decision,
                leaf_node=leaf_node,
                task_id=task.id,
                document_content_by_id=document_content_by_id,
            )
        elif decision.action == "add_leaf":
            leaf_node = new_leaf_by_candidate_id.get(candidate.id)
            if leaf_node is None:
                candidate.status = TaxonomyCandidateStatus.NEEDS_HANDLING
                continue
            candidate.status = TaxonomyCandidateStatus.TASK_ADDED
            _add_task_generated_tag(
                db_session=db_session,
                document_id=candidate.document_id,
                leaf_node=leaf_node,
                version_id=leaf_node.version_id,
                task_id=task.id,
                confidence=candidate.confidence,
                evidence=candidate.evidence,
                reason=decision.reason,
                tagging_source_content=document_content_by_id.get(
                    candidate.document_id, candidate.evidence
                ),
            )
        elif decision.action == "reject":
            candidate.status = TaxonomyCandidateStatus.REJECTED
        else:
            candidate.status = TaxonomyCandidateStatus.NEEDS_HANDLING


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
    document_by_id = {document.id: document for document in documents}
    candidate_labels: list[TaxonomyCandidateLabel] = []
    document_content_by_id: dict[str, str] = {}
    failed_document_ids: set[str] = set()

    for document in documents:
        try:
            content = _tagging_content(
                document=document,
                db_session=db_session,
                source=request.source,
            )
            document_content_by_id[document.id] = content
            result = recommend_taxonomy_tags(
                document_title=document.semantic_id,
                document_content=content,
                leaf_nodes=leaf_nodes,
                enable_optimization=request.enable_optimization,
                active_confidence_threshold=TAXONOMY_TAG_CONFIDENCE_ACTIVE_THRESHOLD,
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
                if (
                    request.enable_optimization
                    and recommendation.confidence
                    < TAXONOMY_TAG_CONFIDENCE_ACTIVE_THRESHOLD
                ):
                    candidate_labels.append(
                        _add_low_confidence_leaf_candidate(
                            db_session=db_session,
                            task_id=task.id,
                            document_id=document.id,
                            leaf_node=leaf_node,
                            confidence=recommendation.confidence,
                            evidence=recommendation.evidence,
                            unmatched_reason=result.unmatched_reason,
                        )
                    )
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
                        status=TaxonomyAssignmentStatus.ACTIVE,
                    )
                )

            for candidate in result.candidates:
                candidate_label = TaxonomyCandidateLabel(
                    task_id=task.id,
                    document_id=document.id,
                    candidate_path=candidate.path,
                    definition=candidate.definition,
                    evidence=candidate.evidence,
                    confidence=candidate.confidence,
                    status=TaxonomyCandidateStatus.PENDING_REVIEW,
                    redundancy_result="pending_health_check",
                    suggested_reuse_node_id=None,
                )
                db_session.add(candidate_label)
                candidate_labels.append(candidate_label)

            task.processed_docs += 1
        except Exception as e:
            logger.exception("Failed to taxonomy-tag document %s", document.id)
            task.failed_docs += 1
            task.error_message = str(e)
            failed_document_ids.add(document.id)
            _add_tagging_failed_marker(
                db_session=db_session,
                document_id=document.id,
                version_id=version.id,
                task_id=task.id,
                failure_reason=str(e),
                tagging_source_content=document_content_by_id.get(document.id, ""),
            )

    try:
        _process_candidate_labels_after_batch(
            db_session=db_session,
            task=task,
            version=version,
            candidate_labels=candidate_labels,
            document_content_by_id=document_content_by_id,
            created_by_user_id=created_by_user_id,
            llm=llm,
        )
        db_session.flush()
        fallback_version = get_active_taxonomy_version(db_session) or version
        fallback_leaf_nodes = _active_leaf_nodes(db_session, fallback_version.id)
        for document_id, content in document_content_by_id.items():
            if document_id in failed_document_ids:
                continue
            if _has_successful_taxonomy_tag(
                db_session,
                document_id=document_id,
                task_id=task.id,
            ):
                continue
            document = document_by_id.get(document_id)
            if document is not None:
                try:
                    if _add_existing_label_fallback_tags(
                        db_session=db_session,
                        document=document,
                        content=content,
                        leaf_nodes=fallback_leaf_nodes,
                        task=task,
                        llm=llm,
                    ):
                        continue
                except Exception as e:
                    logger.exception(
                        "Failed fallback taxonomy-tagging for document %s",
                        document_id,
                    )
                    task.error_message = str(e)
            failed_document_ids.add(document_id)
            task.failed_docs += 1
            reason = "未匹配到可用标签，需要人工处理"
            task.error_message = task.error_message or reason
            _add_tagging_failed_marker(
                db_session=db_session,
                document_id=document_id,
                version_id=version.id,
                task_id=task.id,
                failure_reason=reason,
                tagging_source_content=content,
            )
        for document_id in set(document_content_by_id):
            project_taxonomy_tags_to_document_metadata(
                db_session,
                document_id=document_id,
            )
    except Exception as e:
        logger.exception("Failed to process taxonomy candidate labels for task %s", task.id)
        failed_candidate_document_ids = {
            candidate.document_id for candidate in candidate_labels
        }
        task.failed_docs += len(failed_candidate_document_ids)
        task.error_message = str(e)
        for document_id in failed_candidate_document_ids:
            failed_document_ids.add(document_id)
            _add_tagging_failed_marker(
                db_session=db_session,
                document_id=document_id,
                version_id=version.id,
                task_id=task.id,
                failure_reason=str(e),
                tagging_source_content=document_content_by_id.get(document_id, ""),
            )

    task.completed_at = datetime.now(timezone.utc)
    task.status = (
        TaxonomyTaggingTaskStatus.COMPLETE
        if task.failed_docs == 0
        else TaxonomyTaggingTaskStatus.COMPLETED_WITH_ERRORS
    )
    db_session.commit()
    return task
