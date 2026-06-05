from __future__ import annotations

import re
import time
from collections import defaultdict

from sqlalchemy.orm import Session

from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.models import TaxonomyNode
from onyx.db.taxonomy import get_active_nodes
from onyx.db.taxonomy import get_node_descendant_leaf_ids
from onyx.server.settings.models import Settings
from onyx.taxonomy.models import TaxonomyCandidateMatch
from onyx.taxonomy.models import TaxonomySearchApplyTo
from onyx.taxonomy.models import TaxonomySearchConfig
from onyx.taxonomy.models import TaxonomySearchDecision
from onyx.taxonomy.models import TaxonomySearchMode
from onyx.taxonomy.models import TaxonomySearchRecommendedAction


def _settings_to_taxonomy_config(settings: Settings) -> TaxonomySearchConfig:
    return TaxonomySearchConfig(**settings.model_dump())


def _tokenize(query: str) -> set[str]:
    lowered = query.lower()
    tokens = set(re.findall(r"[0-9a-zA-Z_\-\u4e00-\u9fff]+", lowered))
    for char in lowered:
        if "\u4e00" <= char <= "\u9fff":
            tokens.add(char)
    return tokens


def _node_card_terms(node: TaxonomyNode) -> tuple[list[str], list[str]]:
    strong_terms = [node.name, node.display_name or "", *(node.keywords or []), *(node.synonyms or [])]
    weak_terms = [
        node.full_path,
        node.definition,
        node.applicability,
        *(node.positive_examples or []),
        *(node.negative_examples or []),
    ]
    return strong_terms, weak_terms


def _score_node(query: str, query_tokens: set[str], node: TaxonomyNode) -> tuple[float, str]:
    query_lower = query.lower()
    strong_terms, weak_terms = _node_card_terms(node)
    score = 0.0
    basis: list[str] = []

    for term in strong_terms:
        normalized = term.strip().lower()
        if not normalized:
            continue
        if normalized in query_lower:
            score += 0.55 if normalized == node.name.lower() else 0.35
            basis.append(term)
            continue
        term_tokens = _tokenize(normalized)
        if term_tokens and term_tokens.issubset(query_tokens):
            score += 0.25
            basis.append(term)

    weak_text = " ".join(weak_terms).lower()
    weak_tokens = _tokenize(weak_text)
    overlap = len(query_tokens & weak_tokens)
    if overlap:
        score += min(0.35, overlap * 0.04)
        basis.append("definition/keywords overlap")

    if node.level == TaxonomyNodeLevel.LEAF:
        score += 0.03
    return min(1.0, score), ", ".join(dict.fromkeys(basis)) or "text overlap"


def _threshold_for_level(
    config: TaxonomySearchConfig, level: TaxonomyNodeLevel
) -> float:
    if level == TaxonomyNodeLevel.LEAF:
        return (
            config.taxonomy_search_leaf_confidence_threshold
            or config.taxonomy_search_default_confidence_threshold
        )
    if level == TaxonomyNodeLevel.L2:
        return (
            config.taxonomy_search_l2_confidence_threshold
            or config.taxonomy_search_default_confidence_threshold
        )
    return (
        config.taxonomy_search_l1_confidence_threshold
        or config.taxonomy_search_default_confidence_threshold
    )


def _path_for_node(node: TaxonomyNode, nodes_by_id: dict[str, TaxonomyNode]) -> list[str]:
    return [
        nodes_by_id[node_id].name
        for node_id in node.path_node_ids
        if node_id in nodes_by_id
    ]


def _candidate_from_node(
    node: TaxonomyNode,
    nodes_by_id: dict[str, TaxonomyNode],
    confidence: float,
    basis: str,
) -> TaxonomyCandidateMatch:
    return TaxonomyCandidateMatch(
        node_id=node.id,
        node_name=node.name,
        node_level=node.level,
        path=_path_for_node(node, nodes_by_id),
        confidence=confidence,
        basis=basis,
    )


def _aggregate_parent_scores(
    scores: dict[str, tuple[float, str]],
    nodes_by_id: dict[str, TaxonomyNode],
) -> dict[str, tuple[float, str]]:
    children_scores: dict[str, list[float]] = defaultdict(list)
    for node_id, (score, _) in scores.items():
        node = nodes_by_id[node_id]
        if node.parent_id:
            children_scores[node.parent_id].append(score)
        if len(node.path_node_ids) >= 2:
            children_scores[node.path_node_ids[1]].append(score)
        if len(node.path_node_ids) >= 1:
            children_scores[node.path_node_ids[0]].append(score)

    aggregate: dict[str, tuple[float, str]] = {}
    for node_id, child_scores in children_scores.items():
        if node_id not in nodes_by_id or not child_scores:
            continue
        best = max(child_scores)
        density_bonus = min(0.2, max(0, len([s for s in child_scores if s > 0.2]) - 1) * 0.05)
        aggregate[node_id] = (min(1.0, best * 0.88 + density_bonus), "child leaf aggregation")
    return aggregate


def match_taxonomy_query(
    *,
    query: str,
    settings: Settings,
    apply_to: TaxonomySearchApplyTo,
    db_session: Session,
    manual_node_ids: list[str] | None = None,
) -> TaxonomySearchDecision:
    start = time.monotonic()
    config = _settings_to_taxonomy_config(settings)
    manual_node_ids = manual_node_ids or []

    if not config.taxonomy_search_enabled and not manual_node_ids:
        return TaxonomySearchDecision(reason="taxonomy search disabled")

    if config.taxonomy_search_apply_to not in (TaxonomySearchApplyTo.BOTH, apply_to):
        return TaxonomySearchDecision(reason="taxonomy search does not apply to this flow")

    nodes = get_active_nodes(db_session)
    if not nodes:
        return TaxonomySearchDecision(reason="no active taxonomy version")

    nodes_by_id = {node.id: node for node in nodes}
    if manual_node_ids:
        leaf_ids = get_node_descendant_leaf_ids(
            db_session, node_ids=manual_node_ids, active_only=True
        )
        first_node = nodes_by_id.get(manual_node_ids[0])
        return TaxonomySearchDecision(
            matched=bool(leaf_ids),
            node_id=first_node.id if first_node else None,
            node_level=first_node.level if first_node else None,
            path=_path_for_node(first_node, nodes_by_id) if first_node else [],
            confidence=1.0 if leaf_ids else 0,
            expanded_leaf_ids=leaf_ids[: config.taxonomy_search_max_leaf_expansion_count],
            recommended_action=TaxonomySearchRecommendedAction.HARD_FILTER,
            reason="manual taxonomy filter",
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )

    if config.taxonomy_search_mode in (TaxonomySearchMode.OFF, TaxonomySearchMode.MANUAL_ONLY):
        return TaxonomySearchDecision(reason="automatic taxonomy matching disabled")

    query_tokens = _tokenize(query)
    scores: dict[str, tuple[float, str]] = {}
    for node in nodes:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if elapsed_ms > config.taxonomy_search_timeout_ms:
            return TaxonomySearchDecision(
                reason="taxonomy matching timed out",
                timed_out=True,
                elapsed_ms=elapsed_ms,
            )
        score, basis = _score_node(query, query_tokens, node)
        if score > 0:
            scores[node.id] = (score, basis)

    scores.update(
        {
            node_id: max((scores.get(node_id, (0, "")), aggregate), key=lambda item: item[0])
            for node_id, aggregate in _aggregate_parent_scores(scores, nodes_by_id).items()
        }
    )

    candidates = sorted(
        [
            _candidate_from_node(nodes_by_id[node_id], nodes_by_id, score, basis)
            for node_id, (score, basis) in scores.items()
            if node_id in nodes_by_id
        ],
        key=lambda candidate: candidate.confidence,
        reverse=True,
    )[:10]

    for level in [
        TaxonomyNodeLevel.LEAF,
        TaxonomyNodeLevel.L2,
        TaxonomyNodeLevel.L1,
    ]:
        level_candidates = [
            candidate for candidate in candidates if candidate.node_level == level
        ]
        if not level_candidates:
            continue
        best = level_candidates[0]
        threshold = _threshold_for_level(config, level)
        if best.confidence < threshold:
            if not config.taxonomy_search_enable_hierarchy_fallback:
                break
            continue
        leaf_ids = get_node_descendant_leaf_ids(
            db_session, node_ids=[best.node_id], active_only=True
        )
        if not leaf_ids:
            return TaxonomySearchDecision(
                candidates=candidates,
                reason="matched node had no active leaf descendants",
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )
        if len(leaf_ids) > config.taxonomy_search_max_leaf_expansion_count:
            return TaxonomySearchDecision(
                matched=True,
                node_id=best.node_id,
                node_level=best.node_level,
                path=best.path,
                confidence=best.confidence,
                candidates=candidates,
                expanded_leaf_ids=[],
                recommended_action=TaxonomySearchRecommendedAction.SUGGEST,
                reason="leaf expansion count exceeded configured maximum",
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

        action = TaxonomySearchRecommendedAction.SUGGEST
        if config.taxonomy_search_mode == TaxonomySearchMode.SUGGEST_ONLY:
            action = TaxonomySearchRecommendedAction.SUGGEST
        elif config.taxonomy_search_mode == TaxonomySearchMode.SOFT_FILTER_WITH_FALLBACK:
            action = TaxonomySearchRecommendedAction.SOFT_FILTER
        elif config.taxonomy_search_mode == TaxonomySearchMode.HARD_FILTER:
            if level == TaxonomyNodeLevel.L2 and not config.taxonomy_search_allow_l2_hard_filter:
                action = TaxonomySearchRecommendedAction.SOFT_FILTER
            elif level == TaxonomyNodeLevel.L1 and not config.taxonomy_search_allow_l1_hard_filter:
                action = TaxonomySearchRecommendedAction.SOFT_FILTER
            else:
                action = TaxonomySearchRecommendedAction.HARD_FILTER

        return TaxonomySearchDecision(
            matched=True,
            node_id=best.node_id,
            node_level=best.node_level,
            path=best.path,
            confidence=best.confidence,
            candidates=candidates,
            expanded_leaf_ids=leaf_ids,
            recommended_action=action,
            reason=f"{level.value} confidence passed threshold",
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )

    return TaxonomySearchDecision(
        candidates=candidates,
        reason="no taxonomy candidate passed configured threshold",
        elapsed_ms=int((time.monotonic() - start) * 1000),
    )
