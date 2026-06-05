from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from datetime import timezone
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.db.enums import TaxonomyAssignmentStatus
from onyx.db.enums import TaxonomyCandidateStatus
from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.enums import TaxonomyNodeSource
from onyx.db.enums import TaxonomyReviewStatus
from onyx.db.enums import TaxonomyTaggingSource
from onyx.db.enums import TaxonomyTaggingTaskStatus
from onyx.db.enums import TaxonomyTagSource
from onyx.db.enums import TaxonomyVersionSource
from onyx.db.models import Document
from onyx.db.models import DocumentTaxonomyTag
from onyx.db.models import TaxonomyCandidateLabel
from onyx.db.models import TaxonomyNode
from onyx.db.models import TaxonomyTaggingTask
from onyx.db.taxonomy import create_taxonomy_version_from_tree
from onyx.db.taxonomy import get_active_taxonomy_version
from onyx.kg.models import KGStage
from onyx.llm.interfaces import LLM
from onyx.taxonomy.constants import TAXONOMY_PROMPT_VERSION
from onyx.taxonomy.llm_service import TaxonomyCandidateHealthDecision
from onyx.taxonomy.models import TaxonomyNodeCreate
from onyx.taxonomy.service import _process_candidate_labels_after_batch


@pytest.fixture
def taxonomy_session(
    db_session: Session,
    tenant_context: None,  # noqa: ARG001
) -> Generator[Session, None, None]:
    try:
        yield db_session
    finally:
        db_session.rollback()


def _taxonomy_tree() -> list[TaxonomyNodeCreate]:
    return [
        TaxonomyNodeCreate(
            id="support_root",
            code="support_root",
            level=TaxonomyNodeLevel.L1,
            name="客户服务",
            definition="客户服务相关内容",
            applicability="客户咨询、售后和问题处理",
            keywords=["客户服务"],
            children=[
                TaxonomyNodeCreate(
                    id="support_after_sale",
                    code="support",
                    level=TaxonomyNodeLevel.L2,
                    name="售后处理",
                    definition="售后问题处理流程",
                    applicability="维修、排查、工单处理",
                    keywords=["售后"],
                    children=[
                        TaxonomyNodeCreate(
                            id="support_fault",
                            code="fault",
                            level=TaxonomyNodeLevel.LEAF,
                            name="故障排查",
                            definition="产品故障定位和排查步骤",
                            applicability="故障现象、排查路径、解决方案",
                            keywords=["故障"],
                            positive_examples=["设备无法启动"],
                            negative_examples=["产品功能介绍"],
                        )
                    ],
                )
            ],
        )
    ]


def _node_by_code(
    db_session: Session,
    *,
    version_id: int,
    code: str,
) -> TaxonomyNode:
    node = db_session.scalar(
        select(TaxonomyNode).where(
            TaxonomyNode.version_id == version_id,
            TaxonomyNode.code == code,
        )
    )
    assert node is not None
    return node


def _add_document(db_session: Session, document_id: str) -> None:
    db_session.add(
        Document(
            id=document_id,
            semantic_id=document_id,
            kg_stage=KGStage.NOT_STARTED,
        )
    )


def _add_candidate(
    db_session: Session,
    *,
    task_id: int,
    document_id: str,
    leaf_name: str,
) -> TaxonomyCandidateLabel:
    candidate = TaxonomyCandidateLabel(
        task_id=task_id,
        document_id=document_id,
        candidate_path=["客户服务", "售后处理", leaf_name],
        definition=f"{leaf_name}定义",
        evidence=f"{leaf_name}证据",
        confidence=0.82,
        status=TaxonomyCandidateStatus.PENDING_REVIEW,
        redundancy_result="pending_health_check",
    )
    db_session.add(candidate)
    return candidate


def test_candidate_health_flow_batches_reuse_and_new_leaf_binding(
    taxonomy_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = create_taxonomy_version_from_tree(
        taxonomy_session,
        nodes=_taxonomy_tree(),
        taxonomy_name=f"test-taxonomy-{uuid4().hex}",
        industry_context=None,
        company_description=None,
        source=TaxonomyVersionSource.MANUAL,
        change_summary="Test taxonomy",
        change_reason="Test taxonomy",
        created_by_user_id=None,
        activate=True,
    )
    taxonomy_session.flush()
    support_l2 = _node_by_code(
        taxonomy_session,
        version_id=version.id,
        code="support",
    )
    fault_leaf = _node_by_code(
        taxonomy_session,
        version_id=version.id,
        code="fault",
    )

    doc_existing = f"taxonomy-flow-existing-{uuid4().hex}"
    doc_reuse = f"taxonomy-flow-reuse-{uuid4().hex}"
    doc_new = f"taxonomy-flow-new-{uuid4().hex}"
    for document_id in [doc_existing, doc_reuse, doc_new]:
        _add_document(taxonomy_session, document_id)

    task = TaxonomyTaggingTask(
        version_id=version.id,
        status=TaxonomyTaggingTaskStatus.RUNNING,
        source=TaxonomyTaggingSource.SUMMARY,
        enable_optimization=True,
        optimization_strength="balanced",
        total_docs=3,
        processed_docs=3,
        failed_docs=0,
        started_at=datetime.now(timezone.utc),
    )
    taxonomy_session.add(task)
    taxonomy_session.flush()

    taxonomy_session.add(
        DocumentTaxonomyTag(
            document_id=doc_existing,
            leaf_node_id=fault_leaf.id,
            version_id=version.id,
            task_id=task.id,
            full_path_snapshot=fault_leaf.full_path,
            confidence=0.91,
            source=TaxonomyTagSource.AI_RECOMMENDED,
            is_primary=True,
            sort_order=0,
            evidence="原始故障证据",
            tagging_source_content="原始故障正文",
            prompt_version=TAXONOMY_PROMPT_VERSION,
            review_status=TaxonomyReviewStatus.UNCONFIRMED,
            status=TaxonomyAssignmentStatus.ACTIVE,
        )
    )
    reuse_candidate = _add_candidate(
        taxonomy_session,
        task_id=task.id,
        document_id=doc_reuse,
        leaf_name="故障排查别名",
    )
    new_candidate_one = _add_candidate(
        taxonomy_session,
        task_id=task.id,
        document_id=doc_reuse,
        leaf_name="远程诊断",
    )
    new_candidate_two = _add_candidate(
        taxonomy_session,
        task_id=task.id,
        document_id=doc_new,
        leaf_name="远程诊断",
    )
    taxonomy_session.flush()

    def fake_review_candidate_labels(
        *_args: object,
        **_kwargs: object,
    ) -> list[TaxonomyCandidateHealthDecision]:
        return [
            TaxonomyCandidateHealthDecision(
                candidate_id=reuse_candidate.id,
                action="reuse_existing",
                reason="已有故障排查可覆盖",
                suggested_reuse_node_id=fault_leaf.id,
            ),
            TaxonomyCandidateHealthDecision(
                candidate_id=new_candidate_one.id,
                action="add_leaf",
                reason="补充最小粒度远程诊断 leaf",
                parent_l2_node_id=support_l2.id,
                leaf_name="远程诊断",
                definition="远程排查和诊断设备问题",
                applicability="远程日志、远程检测、远程定位",
                keywords=["远程诊断"],
                synonyms=["远程排查"],
                positive_examples=["通过远程日志定位故障"],
                negative_examples=["线下维修排期"],
            ),
            TaxonomyCandidateHealthDecision(
                candidate_id=new_candidate_two.id,
                action="add_leaf",
                reason="批内重复候选复用同一新增 leaf",
                parent_l2_node_id=support_l2.id,
                leaf_name="远程诊断",
                definition="远程排查和诊断设备问题",
                applicability="远程日志、远程检测、远程定位",
                keywords=["远程诊断"],
                synonyms=["远程排查"],
                positive_examples=["通过远程日志定位故障"],
                negative_examples=["线下维修排期"],
            ),
        ]

    monkeypatch.setattr(
        "onyx.taxonomy.service.review_taxonomy_candidate_labels",
        fake_review_candidate_labels,
    )

    _process_candidate_labels_after_batch(
        db_session=taxonomy_session,
        task=task,
        version=version,
        candidate_labels=[reuse_candidate, new_candidate_one, new_candidate_two],
        document_content_by_id={
            doc_existing: "原始故障正文",
            doc_reuse: "故障和远程诊断正文",
            doc_new: "远程诊断正文",
        },
        created_by_user_id=None,
        llm=cast(LLM, object()),
    )
    taxonomy_session.flush()

    active_version = get_active_taxonomy_version(taxonomy_session)
    assert active_version is not None
    assert active_version.id != version.id
    assert active_version.source == TaxonomyVersionSource.TAGGING_OPTIMIZATION

    new_remote_leaves = list(
        taxonomy_session.scalars(
            select(TaxonomyNode).where(
                TaxonomyNode.version_id == active_version.id,
                TaxonomyNode.level == TaxonomyNodeLevel.LEAF,
                TaxonomyNode.source == TaxonomyNodeSource.TASK_GENERATED,
                TaxonomyNode.name == "远程诊断",
            )
        ).all()
    )
    assert len(new_remote_leaves) == 1
    new_remote_leaf = new_remote_leaves[0]

    taxonomy_session.refresh(reuse_candidate)
    taxonomy_session.refresh(new_candidate_one)
    taxonomy_session.refresh(new_candidate_two)
    assert reuse_candidate.status == TaxonomyCandidateStatus.REUSED_EXISTING
    assert new_candidate_one.status == TaxonomyCandidateStatus.TASK_ADDED
    assert new_candidate_two.status == TaxonomyCandidateStatus.TASK_ADDED

    remapped_fault_leaf = _node_by_code(
        taxonomy_session,
        version_id=active_version.id,
        code="fault",
    )
    assert reuse_candidate.suggested_reuse_node_id == remapped_fault_leaf.id

    active_tags = list(
        taxonomy_session.scalars(
            select(DocumentTaxonomyTag).where(
                DocumentTaxonomyTag.task_id == task.id,
                DocumentTaxonomyTag.status == TaxonomyAssignmentStatus.ACTIVE,
            )
        ).all()
    )
    assert {tag.version_id for tag in active_tags} == {active_version.id}

    existing_doc_tags = [tag for tag in active_tags if tag.document_id == doc_existing]
    assert len(existing_doc_tags) == 1
    assert existing_doc_tags[0].leaf_node_id == remapped_fault_leaf.id

    generated_remote_tags = [
        tag for tag in active_tags if tag.leaf_node_id == new_remote_leaf.id
    ]
    assert {tag.document_id for tag in generated_remote_tags} == {doc_reuse, doc_new}


def test_candidate_health_flow_remaps_task_tags_when_no_candidates(
    taxonomy_session: Session,
) -> None:
    version = create_taxonomy_version_from_tree(
        taxonomy_session,
        nodes=_taxonomy_tree(),
        taxonomy_name=f"test-taxonomy-{uuid4().hex}",
        industry_context=None,
        company_description=None,
        source=TaxonomyVersionSource.MANUAL,
        change_summary="Test taxonomy",
        change_reason="Test taxonomy",
        created_by_user_id=None,
        activate=True,
    )
    taxonomy_session.flush()
    fault_leaf = _node_by_code(
        taxonomy_session,
        version_id=version.id,
        code="fault",
    )
    document_id = f"taxonomy-flow-no-candidate-{uuid4().hex}"
    _add_document(taxonomy_session, document_id)
    task = TaxonomyTaggingTask(
        version_id=version.id,
        status=TaxonomyTaggingTaskStatus.RUNNING,
        source=TaxonomyTaggingSource.SUMMARY,
        enable_optimization=True,
        optimization_strength="balanced",
        total_docs=1,
        processed_docs=1,
        failed_docs=0,
        started_at=datetime.now(timezone.utc),
    )
    taxonomy_session.add(task)
    taxonomy_session.flush()
    tag = DocumentTaxonomyTag(
        document_id=document_id,
        leaf_node_id=fault_leaf.id,
        version_id=version.id,
        task_id=task.id,
        full_path_snapshot=fault_leaf.full_path,
        confidence=0.91,
        source=TaxonomyTagSource.AI_RECOMMENDED,
        is_primary=True,
        sort_order=0,
        evidence="原始故障证据",
        tagging_source_content="原始故障正文",
        prompt_version=TAXONOMY_PROMPT_VERSION,
        review_status=TaxonomyReviewStatus.UNCONFIRMED,
        status=TaxonomyAssignmentStatus.ACTIVE,
    )
    taxonomy_session.add(tag)

    latest_version = create_taxonomy_version_from_tree(
        taxonomy_session,
        nodes=_taxonomy_tree(),
        taxonomy_name=None,
        industry_context=None,
        company_description=None,
        source=TaxonomyVersionSource.TAGGING_OPTIMIZATION,
        change_summary="Concurrent taxonomy update",
        change_reason="Concurrent taxonomy update",
        created_by_user_id=None,
        activate=True,
    )
    taxonomy_session.flush()
    latest_fault_leaf = _node_by_code(
        taxonomy_session,
        version_id=latest_version.id,
        code="fault",
    )

    _process_candidate_labels_after_batch(
        db_session=taxonomy_session,
        task=task,
        version=version,
        candidate_labels=[],
        document_content_by_id={document_id: "原始故障正文"},
        created_by_user_id=None,
        llm=cast(LLM, object()),
    )
    taxonomy_session.flush()

    taxonomy_session.refresh(tag)
    assert tag.version_id == latest_version.id
    assert tag.leaf_node_id == latest_fault_leaf.id
    assert tag.full_path_snapshot == latest_fault_leaf.full_path
