from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from datetime import timezone
from uuid import UUID
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from onyx.configs.constants import DocumentSource
from onyx.db.enums import TaxonomyAssignmentStatus
from onyx.db.enums import TaxonomyChangeType
from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.enums import TaxonomyNodeStatus
from onyx.db.enums import TaxonomyScope
from onyx.db.enums import TaxonomySummaryStatus
from onyx.db.enums import TaxonomyVersionStatus
from onyx.db.models import Connector
from onyx.db.models import Document
from onyx.db.models import DocumentByConnectorCredentialPair
from onyx.db.models import DocumentTaxonomySummary
from onyx.db.models import DocumentTaxonomyTag
from onyx.db.models import Taxonomy
from onyx.db.models import TaxonomyChangeRecord
from onyx.db.models import TaxonomyNode
from onyx.db.models import TaxonomyVersion
from onyx.db.tag import create_or_add_document_tag_list
from onyx.taxonomy.constants import DEFAULT_TAXONOMY_NAME
from onyx.taxonomy.constants import TAXONOMY_METADATA_L1_KEY
from onyx.taxonomy.constants import TAXONOMY_METADATA_L2_KEY
from onyx.taxonomy.constants import TAXONOMY_METADATA_LEAF_KEY
from onyx.taxonomy.constants import TAXONOMY_METADATA_PATH_KEY
from onyx.taxonomy.constants import TAXONOMY_METADATA_VERSION_KEY
from onyx.taxonomy.models import DocumentTaxonomySummarySnapshot
from onyx.taxonomy.models import DocumentTaxonomyTagSnapshot
from onyx.taxonomy.models import TaxonomyCoverageStats
from onyx.taxonomy.models import TaxonomyNodeCreate
from onyx.taxonomy.models import TaxonomyNodeSnapshot
from onyx.taxonomy.models import TaxonomySnapshot
from onyx.taxonomy.models import TaxonomyVersionSnapshot


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", value.strip()).strip("_")
    return cleaned.lower() or uuid4().hex[:8]


def get_or_create_taxonomy(
    db_session: Session,
    *,
    name: str | None = None,
    industry_context: str | None = None,
    company_description: str | None = None,
    owner_user_id: UUID | None = None,
) -> Taxonomy:
    taxonomy = db_session.scalar(select(Taxonomy).order_by(Taxonomy.id.asc()).limit(1))
    if taxonomy is not None:
        if name:
            taxonomy.name = name
        if industry_context is not None:
            taxonomy.industry_context = industry_context
        if company_description is not None:
            taxonomy.company_description = company_description
        if owner_user_id is not None and taxonomy.owner_user_id is None:
            taxonomy.owner_user_id = owner_user_id
        return taxonomy

    taxonomy = Taxonomy(
        name=name or DEFAULT_TAXONOMY_NAME,
        scope=TaxonomyScope.ENTERPRISE,
        industry_context=industry_context,
        company_description=company_description,
        owner_user_id=owner_user_id,
    )
    db_session.add(taxonomy)
    db_session.flush()
    return taxonomy


def get_active_taxonomy(db_session: Session) -> Taxonomy | None:
    return db_session.scalar(
        select(Taxonomy)
        .options(
            selectinload(Taxonomy.active_version).selectinload(TaxonomyVersion.nodes)
        )
        .where(Taxonomy.active_version_id.is_not(None))
        .order_by(Taxonomy.id.asc())
        .limit(1)
    )


def get_active_taxonomy_version(db_session: Session) -> TaxonomyVersion | None:
    taxonomy = get_active_taxonomy(db_session)
    return taxonomy.active_version if taxonomy else None


def _iter_nodes_preorder(
    nodes: list[TaxonomyNodeCreate],
    *,
    parent_id: str | None = None,
) -> list[tuple[TaxonomyNodeCreate, str | None]]:
    flattened: list[tuple[TaxonomyNodeCreate, str | None]] = []
    for node in nodes:
        flattened.append((node, parent_id))
        parent_for_children = node.id
        if parent_for_children is None:
            parent_for_children = f"{parent_id or 'taxonomy'}.{_slugify(node.name)}"
            node.id = parent_for_children
        flattened.extend(_iter_nodes_preorder(node.children, parent_id=parent_for_children))
    return flattened


def _selected_template_tree(
    nodes: list[TaxonomyNodeCreate],
    selected_leaf_ids: set[str],
) -> list[TaxonomyNodeCreate]:
    selected: list[TaxonomyNodeCreate] = []
    for node in nodes:
        if node.level == TaxonomyNodeLevel.LEAF:
            if node.id in selected_leaf_ids:
                selected.append(node)
            continue
        children = _selected_template_tree(node.children, selected_leaf_ids)
        if children:
            selected.append(node.model_copy(update={"children": children}, deep=True))
    return selected


def create_taxonomy_version_from_tree(
    db_session: Session,
    *,
    nodes: list[TaxonomyNodeCreate],
    selected_default_leaf_ids: list[str] | None = None,
    taxonomy_name: str | None = None,
    industry_context: str | None = None,
    company_description: str | None = None,
    source,
    change_summary: str,
    change_reason: str | None,
    created_by_user_id: UUID | None,
    activate: bool = False,
) -> TaxonomyVersion:
    from onyx.taxonomy.default_template import get_default_taxonomy_template

    final_nodes: list[TaxonomyNodeCreate] = []
    if selected_default_leaf_ids:
        final_nodes.extend(
            _selected_template_tree(
                get_default_taxonomy_template(), set(selected_default_leaf_ids)
            )
        )
    final_nodes.extend(nodes)
    validate_taxonomy_tree(final_nodes)

    taxonomy = get_or_create_taxonomy(
        db_session,
        name=taxonomy_name,
        industry_context=industry_context,
        company_description=company_description,
        owner_user_id=created_by_user_id,
    )
    next_version_number = (
        db_session.scalar(
            select(func.max(TaxonomyVersion.version_number)).where(
                TaxonomyVersion.taxonomy_id == taxonomy.id
            )
        )
        or 0
    ) + 1

    version = TaxonomyVersion(
        taxonomy_id=taxonomy.id,
        version_number=next_version_number,
        status=(
            TaxonomyVersionStatus.ACTIVE if activate else TaxonomyVersionStatus.DRAFT
        ),
        parent_version_id=taxonomy.active_version_id,
        source=source,
        change_summary=change_summary,
        change_reason=change_reason,
        effective_at=datetime.now(timezone.utc) if activate else None,
        created_by_user_id=created_by_user_id,
        confirmed_by_user_id=created_by_user_id if activate else None,
        health_summary=build_health_summary(final_nodes),
    )
    db_session.add(version)
    db_session.flush()

    created_nodes: dict[str, TaxonomyNode] = {}

    def add_node(
        node: TaxonomyNodeCreate,
        parent: TaxonomyNode | None,
        path_names: list[str],
        path_ids: list[str],
        sort_order: int,
    ) -> None:
        original_node_id = node.id or uuid4().hex[:10]
        node_id = f"v{version.id}.{original_node_id}"
        full_path_names = path_names + [node.name]
        full_path_ids = path_ids + [node_id]
        db_node = TaxonomyNode(
            id=node_id,
            version_id=version.id,
            parent_id=parent.id if parent else None,
            level=node.level,
            code=node.code or original_node_id,
            name=node.name,
            display_name=node.display_name,
            full_path=" / ".join(full_path_names),
            path_node_ids=full_path_ids,
            sort_order=sort_order,
            definition=node.definition,
            applicability=node.applicability,
            exclusion=node.exclusion,
            positive_examples=node.positive_examples,
            negative_examples=node.negative_examples,
            keywords=node.keywords,
            synonyms=node.synonyms,
            tagging_guidance=node.tagging_guidance,
            conflict_rules=node.conflict_rules,
            source=node.source,
            source_detail=node.source_detail,
            status=(
                TaxonomyNodeStatus.ACTIVE if activate else TaxonomyNodeStatus.DRAFT
            ),
            created_by_user_id=created_by_user_id,
            updated_by_user_id=created_by_user_id,
        )
        db_session.add(db_node)
        created_nodes[node_id] = db_node
        for child_index, child in enumerate(node.children):
            add_node(child, db_node, full_path_names, full_path_ids, child_index)

    for index, root in enumerate(final_nodes):
        add_node(root, None, [], [], index)
    db_session.flush()

    db_session.add(
        TaxonomyChangeRecord(
            version_id=version.id,
            change_type=TaxonomyChangeType.CREATE,
            after_snapshot={"node_count": len(created_nodes)},
            reason=change_reason or change_summary,
            created_by_user_id=created_by_user_id,
            confirmed_by_user_id=created_by_user_id if activate else None,
        )
    )

    if activate:
        activate_taxonomy_version(
            db_session, version_id=version.id, user_id=created_by_user_id
        )
    return version


def activate_taxonomy_version(
    db_session: Session, *, version_id: int, user_id: UUID | None
) -> TaxonomyVersion:
    version = db_session.get(TaxonomyVersion, version_id)
    if version is None:
        raise ValueError(f"Taxonomy version {version_id} not found")
    validate_taxonomy_nodes_for_activation(list(version.nodes))

    db_session.execute(
        update(TaxonomyVersion)
        .where(
            TaxonomyVersion.taxonomy_id == version.taxonomy_id,
            TaxonomyVersion.id != version.id,
            TaxonomyVersion.status == TaxonomyVersionStatus.ACTIVE,
        )
        .values(status=TaxonomyVersionStatus.SUPERSEDED)
    )
    version.status = TaxonomyVersionStatus.ACTIVE
    version.effective_at = datetime.now(timezone.utc)
    version.confirmed_by_user_id = user_id
    for node in version.nodes:
        if node.status == TaxonomyNodeStatus.DRAFT:
            node.status = TaxonomyNodeStatus.ACTIVE

    taxonomy = db_session.get(Taxonomy, version.taxonomy_id)
    if taxonomy is None:
        raise ValueError(f"Taxonomy {version.taxonomy_id} not found")
    taxonomy.active_version_id = version.id
    db_session.add(
        TaxonomyChangeRecord(
            version_id=version.id,
            change_type=TaxonomyChangeType.ACTIVATE_VERSION,
            after_snapshot={"version_id": version.id},
            reason="Activated taxonomy version",
            created_by_user_id=user_id,
            confirmed_by_user_id=user_id,
        )
    )
    return version


def validate_taxonomy_tree(nodes: list[TaxonomyNodeCreate]) -> None:
    if not nodes:
        raise ValueError("Taxonomy must include at least one root node")

    def validate_node(node: TaxonomyNodeCreate, expected_level: TaxonomyNodeLevel) -> None:
        if node.level != expected_level:
            raise ValueError(f"Node {node.name} must be {expected_level.value}")
        if not node.definition.strip():
            raise ValueError(f"Node {node.name} must include a definition")
        if not node.applicability.strip():
            raise ValueError(f"Node {node.name} must include applicability")
        if not [keyword for keyword in node.keywords if keyword.strip()]:
            raise ValueError(f"Node {node.name} must include at least one keyword")
        if expected_level == TaxonomyNodeLevel.LEAF:
            if node.children:
                raise ValueError(f"Leaf node {node.name} cannot have children")
            if not [example for example in node.positive_examples if example.strip()]:
                raise ValueError(
                    f"Leaf node {node.name} must include at least one positive example"
                )
            if not [example for example in node.negative_examples if example.strip()]:
                raise ValueError(
                    f"Leaf node {node.name} must include at least one negative example"
                )
            return
        next_level = (
            TaxonomyNodeLevel.L2
            if expected_level == TaxonomyNodeLevel.L1
            else TaxonomyNodeLevel.LEAF
        )
        if not node.children:
            raise ValueError(f"Node {node.name} must include children")
        for child in node.children:
            validate_node(child, next_level)

    for root in nodes:
        validate_node(root, TaxonomyNodeLevel.L1)


def validate_taxonomy_nodes_for_activation(nodes: list[TaxonomyNode]) -> None:
    if not nodes:
        raise ValueError("Taxonomy version has no nodes")
    leaf_count = 0
    by_parent: dict[str | None, list[TaxonomyNode]] = defaultdict(list)
    for node in nodes:
        by_parent[node.parent_id].append(node)
        if not node.definition.strip():
            raise ValueError(f"Node {node.name} must include a definition")
        if not node.applicability.strip():
            raise ValueError(f"Node {node.name} must include applicability")
        if not [keyword for keyword in node.keywords if keyword.strip()]:
            raise ValueError(f"Node {node.name} must include at least one keyword")
        if node.level == TaxonomyNodeLevel.LEAF:
            leaf_count += 1
            if not [example for example in node.positive_examples if example.strip()]:
                raise ValueError(
                    f"Leaf node {node.name} must include at least one positive example"
                )
            if not [example for example in node.negative_examples if example.strip()]:
                raise ValueError(
                    f"Leaf node {node.name} must include at least one negative example"
                )
    if leaf_count == 0:
        raise ValueError("Taxonomy version must include at least one leaf node")
    for node in nodes:
        if node.level != TaxonomyNodeLevel.LEAF and not by_parent.get(node.id):
            raise ValueError(f"Non-leaf node {node.name} must include children")


def build_health_summary(nodes: list[TaxonomyNodeCreate]) -> dict[str, int | list[str]]:
    names_by_level: dict[TaxonomyNodeLevel, list[str]] = defaultdict(list)
    missing_examples: list[str] = []

    def visit(node: TaxonomyNodeCreate) -> None:
        names_by_level[node.level].append(node.name.strip().lower())
        if node.level == TaxonomyNodeLevel.LEAF and (
            not node.positive_examples or not node.negative_examples
        ):
            missing_examples.append(node.name)
        for child in node.children:
            visit(child)

    for root in nodes:
        visit(root)

    duplicate_names: list[str] = []
    for names in names_by_level.values():
        seen: set[str] = set()
        for name in names:
            if name in seen and name not in duplicate_names:
                duplicate_names.append(name)
            seen.add(name)

    return {
        "l1_count": len(names_by_level[TaxonomyNodeLevel.L1]),
        "l2_count": len(names_by_level[TaxonomyNodeLevel.L2]),
        "leaf_count": len(names_by_level[TaxonomyNodeLevel.LEAF]),
        "duplicate_names": duplicate_names,
        "leaf_nodes_missing_examples": missing_examples,
    }


def taxonomy_snapshot(taxonomy: Taxonomy | None) -> TaxonomySnapshot | None:
    if taxonomy is None:
        return None
    return TaxonomySnapshot(
        id=taxonomy.id,
        name=taxonomy.name,
        active_version_id=taxonomy.active_version_id,
        industry_context=taxonomy.industry_context,
        company_description=taxonomy.company_description,
        created_at=taxonomy.created_at,
        updated_at=taxonomy.updated_at,
        active_version=taxonomy_version_snapshot(taxonomy.active_version)
        if taxonomy.active_version
        else None,
    )


def taxonomy_version_snapshot(
    version: TaxonomyVersion | None,
) -> TaxonomyVersionSnapshot | None:
    if version is None:
        return None
    nodes = sorted(version.nodes, key=lambda node: (node.sort_order, node.name))
    children_by_parent: dict[str | None, list[TaxonomyNode]] = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node)

    def build_node(node: TaxonomyNode) -> TaxonomyNodeSnapshot:
        return TaxonomyNodeSnapshot(
            id=node.id,
            version_id=node.version_id,
            parent_id=node.parent_id,
            level=node.level,
            code=node.code,
            name=node.name,
            display_name=node.display_name,
            full_path=node.full_path,
            path_node_ids=node.path_node_ids,
            definition=node.definition,
            applicability=node.applicability,
            exclusion=node.exclusion,
            positive_examples=node.positive_examples,
            negative_examples=node.negative_examples,
            keywords=node.keywords,
            synonyms=node.synonyms,
            tagging_guidance=node.tagging_guidance,
            conflict_rules=node.conflict_rules,
            source=node.source,
            source_detail=node.source_detail,
            status=node.status,
            sort_order=node.sort_order,
            children=[build_node(child) for child in children_by_parent.get(node.id, [])],
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    return TaxonomyVersionSnapshot(
        id=version.id,
        taxonomy_id=version.taxonomy_id,
        version_number=version.version_number,
        status=version.status,
        source=version.source,
        change_summary=version.change_summary,
        change_reason=version.change_reason,
        effective_at=version.effective_at,
        health_summary=version.health_summary,
        created_at=version.created_at,
        updated_at=version.updated_at,
        nodes=[build_node(node) for node in children_by_parent.get(None, [])],
    )


def get_active_nodes(db_session: Session) -> list[TaxonomyNode]:
    version = get_active_taxonomy_version(db_session)
    if not version:
        return []
    return list(
        db_session.scalars(
            select(TaxonomyNode)
            .where(
                TaxonomyNode.version_id == version.id,
                TaxonomyNode.status == TaxonomyNodeStatus.ACTIVE,
            )
            .order_by(TaxonomyNode.sort_order, TaxonomyNode.name)
        ).all()
    )


def get_node_descendant_leaf_ids(
    db_session: Session,
    *,
    node_ids: list[str],
    active_only: bool = True,
) -> list[str]:
    if not node_ids:
        return []
    version = get_active_taxonomy_version(db_session)
    if not version:
        return []
    nodes = list(
        db_session.scalars(
            select(TaxonomyNode).where(TaxonomyNode.version_id == version.id)
        ).all()
    )
    node_id_set = set(node_ids)
    children_by_parent: dict[str | None, list[TaxonomyNode]] = defaultdict(list)
    node_by_id = {node.id: node for node in nodes}
    for node in nodes:
        children_by_parent[node.parent_id].append(node)

    leaf_ids: list[str] = []

    def collect(node: TaxonomyNode) -> None:
        if active_only and node.status != TaxonomyNodeStatus.ACTIVE:
            return
        if node.level == TaxonomyNodeLevel.LEAF:
            leaf_ids.append(node.id)
            return
        for child in children_by_parent.get(node.id, []):
            collect(child)

    for node_id in node_id_set:
        node = node_by_id.get(node_id)
        if node:
            collect(node)
    return sorted(set(leaf_ids))


def get_document_source(
    db_session: Session,
    *,
    document_id: str,
) -> DocumentSource | None:
    return db_session.scalar(
        select(Connector.source)
        .join(
            DocumentByConnectorCredentialPair,
            DocumentByConnectorCredentialPair.connector_id == Connector.id,
        )
        .where(DocumentByConnectorCredentialPair.id == document_id)
        .limit(1)
    )


def project_taxonomy_tags_to_document_metadata(
    db_session: Session,
    *,
    document_id: str,
) -> None:
    source = get_document_source(db_session, document_id=document_id)
    if source is None:
        return

    active_tags = list(
        db_session.scalars(
            select(DocumentTaxonomyTag)
            .options(selectinload(DocumentTaxonomyTag.leaf_node))
            .where(
                DocumentTaxonomyTag.document_id == document_id,
                DocumentTaxonomyTag.status == TaxonomyAssignmentStatus.ACTIVE,
                DocumentTaxonomyTag.leaf_node_id.is_not(None),
            )
        ).all()
    )
    if not active_tags:
        return

    leaf_ids: list[str] = []
    l1_ids: list[str] = []
    l2_ids: list[str] = []
    paths: list[str] = []
    version_ids: list[str] = []
    for tag in active_tags:
        if tag.leaf_node_id:
            leaf_ids.append(tag.leaf_node_id)
        if tag.leaf_node and len(tag.leaf_node.path_node_ids) >= 3:
            l1_ids.append(tag.leaf_node.path_node_ids[0])
            l2_ids.append(tag.leaf_node.path_node_ids[1])
        paths.append(tag.full_path_snapshot)
        if tag.version_id is not None:
            version_ids.append(str(tag.version_id))

    tag_values = {
        TAXONOMY_METADATA_VERSION_KEY: sorted(set(version_ids)),
        TAXONOMY_METADATA_L1_KEY: sorted(set(l1_ids)),
        TAXONOMY_METADATA_L2_KEY: sorted(set(l2_ids)),
        TAXONOMY_METADATA_LEAF_KEY: sorted(set(leaf_ids)),
        TAXONOMY_METADATA_PATH_KEY: sorted(set(paths)),
    }
    for key, values in tag_values.items():
        if values:
            create_or_add_document_tag_list(
                tag_key=key,
                tag_values=values,
                source=source,
                document_id=document_id,
                db_session=db_session,
            )


def invalidate_active_document_taxonomy_tags(
    db_session: Session,
    *,
    document_id: str,
    reason: str,
) -> None:
    db_session.execute(
        update(DocumentTaxonomyTag)
        .where(
            DocumentTaxonomyTag.document_id == document_id,
            DocumentTaxonomyTag.status == TaxonomyAssignmentStatus.ACTIVE,
        )
        .values(
            status=TaxonomyAssignmentStatus.NEEDS_RETAG,
            invalidation_reason=reason,
        )
    )


def upsert_document_summary(
    db_session: Session,
    *,
    document_id: str,
    summary: str | None,
    status: TaxonomySummaryStatus,
    is_manual: bool,
    failure_reason: str | None = None,
    model_info: dict | None = None,
) -> DocumentTaxonomySummary:
    existing = db_session.get(DocumentTaxonomySummary, document_id)
    if existing is None:
        existing = DocumentTaxonomySummary(document_id=document_id)
        db_session.add(existing)
    existing.summary = summary
    existing.status = status
    existing.is_manual = is_manual
    existing.failure_reason = failure_reason
    existing.model_info = model_info
    existing.generated_at = (
        datetime.now(timezone.utc)
        if status == TaxonomySummaryStatus.COMPLETE
        else existing.generated_at
    )
    if is_manual:
        invalidate_active_document_taxonomy_tags(
            db_session,
            document_id=document_id,
            reason="Summary was manually edited",
        )
    return existing


def get_document_summaries(
    db_session: Session,
    *,
    limit: int = 50,
) -> list[DocumentTaxonomySummarySnapshot]:
    rows = db_session.execute(
        select(Document, DocumentTaxonomySummary)
        .outerjoin(
            DocumentTaxonomySummary,
            DocumentTaxonomySummary.document_id == Document.id,
        )
        .order_by(Document.last_modified.desc())
        .limit(limit)
    ).all()
    snapshots: list[DocumentTaxonomySummarySnapshot] = []
    for document, summary in rows:
        if summary:
            snapshots.append(
                DocumentTaxonomySummarySnapshot(
                    document_id=document.id,
                    semantic_id=document.semantic_id,
                    summary=summary.summary,
                    status=summary.status,
                    is_manual=summary.is_manual,
                    failure_reason=summary.failure_reason,
                    generated_at=summary.generated_at,
                    updated_at=summary.updated_at,
                    current_label_status=None,
                )
            )
        else:
            snapshots.append(
                DocumentTaxonomySummarySnapshot(
                    document_id=document.id,
                    semantic_id=document.semantic_id,
                    summary=None,
                    status=TaxonomySummaryStatus.PENDING,
                    is_manual=False,
                    failure_reason=None,
                    generated_at=None,
                    updated_at=document.last_modified,
                    current_label_status=None,
                )
            )
    return snapshots


def get_taxonomy_coverage(db_session: Session) -> TaxonomyCoverageStats:
    total_documents = db_session.scalar(select(func.count(Document.id))) or 0
    labeled_documents = (
        db_session.scalar(
            select(func.count(func.distinct(DocumentTaxonomyTag.document_id))).where(
                DocumentTaxonomyTag.status == TaxonomyAssignmentStatus.ACTIVE
            )
        )
        or 0
    )
    coverage = (
        round((labeled_documents / total_documents) * 100, 2)
        if total_documents
        else 0.0
    )
    return TaxonomyCoverageStats(
        total_documents=total_documents,
        labeled_documents=labeled_documents,
        coverage_percent=coverage,
    )


def document_taxonomy_tag_snapshot(
    tag: DocumentTaxonomyTag,
) -> DocumentTaxonomyTagSnapshot:
    return DocumentTaxonomyTagSnapshot(
        id=tag.id,
        document_id=tag.document_id,
        leaf_node_id=tag.leaf_node_id,
        full_path_snapshot=tag.full_path_snapshot,
        confidence=tag.confidence,
        source=tag.source,
        is_primary=tag.is_primary,
        evidence=tag.evidence,
        unmatched_reason=tag.unmatched_reason,
        review_status=tag.review_status,
        status=tag.status,
        created_at=tag.created_at,
        updated_at=tag.updated_at,
    )


def leaf_metadata_tags_from_leaf_ids(leaf_ids: list[str]) -> list[str]:
    return sorted(set(leaf_ids))
