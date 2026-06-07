from __future__ import annotations

import math
import time
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock

from sqlalchemy.orm import Session

from onyx.context.search.utils import get_query_embedding
from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.models import TaxonomyNode
from onyx.db.search_settings import get_current_search_settings
from onyx.db.taxonomy import get_active_nodes
from onyx.db.taxonomy import get_node_descendant_leaf_ids
from onyx.natural_language_processing.search_nlp_models import EmbeddingModel
from onyx.server.settings.models import Settings
from onyx.taxonomy.models import TaxonomyCandidateMatch
from onyx.taxonomy.models import TaxonomySearchApplyTo
from onyx.taxonomy.models import TaxonomySearchConfig
from onyx.taxonomy.models import TaxonomySearchDecision
from onyx.taxonomy.models import TaxonomySearchMode
from onyx.taxonomy.models import TaxonomySearchRecommendedAction
from shared_configs.configs import MODEL_SERVER_HOST
from shared_configs.configs import MODEL_SERVER_PORT
from shared_configs.enums import EmbedTextType
from shared_configs.model_server_models import Embedding

_NAME_SCORE_WEIGHT = 0.4
_DEFINITION_SCORE_WEIGHT = 0.6
_MAX_CANDIDATES = 10


@dataclass(frozen=True)
class _LeafEmbeddingCard:
    node_id: str
    name_embedding: Embedding
    definition_embedding: Embedding


_LEAF_EMBEDDING_CACHE: dict[tuple[str, str], list[_LeafEmbeddingCard]] = {}
_LEAF_EMBEDDING_CACHE_LOCK = Lock()


def _settings_to_taxonomy_config(settings: Settings) -> TaxonomySearchConfig:
    return TaxonomySearchConfig(**settings.model_dump())


def _threshold_for_leaf(config: TaxonomySearchConfig) -> float:
    return (
        config.taxonomy_search_leaf_confidence_threshold
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
    name_score: float | None = None,
    definition_score: float | None = None,
) -> TaxonomyCandidateMatch:
    return TaxonomyCandidateMatch(
        node_id=node.id,
        node_name=node.name,
        node_level=node.level,
        path=_path_for_node(node, nodes_by_id),
        confidence=confidence,
        basis=basis,
        name_score=name_score,
        definition_score=definition_score,
    )


def _manual_taxonomy_decision(
    *,
    manual_node_ids: list[str],
    config: TaxonomySearchConfig,
    nodes_by_id: dict[str, TaxonomyNode],
    db_session: Session,
    start: float,
) -> TaxonomySearchDecision:
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


def _leaf_embedding_cache_key(
    nodes: list[TaxonomyNode], embedding_model: EmbeddingModel
) -> tuple[str, str]:
    version_ids = sorted({str(node.version_id) for node in nodes})
    node_fingerprint = "|".join(
        f"{node.id}:{node.full_path}:{node.definition}" for node in nodes
    )
    model_fingerprint = "|".join(
        [
            embedding_model.model_name or "",
            str(embedding_model.provider_type or ""),
            str(embedding_model.api_url or ""),
            str(embedding_model.reduced_dimension or ""),
            str(embedding_model.normalize),
            str(embedding_model.query_prefix or ""),
            str(embedding_model.passage_prefix or ""),
        ]
    )
    node_digest = sha256(node_fingerprint.encode("utf-8")).hexdigest()
    return (";".join(version_ids) + "|" + node_digest, model_fingerprint)


def _leaf_name_text(node: TaxonomyNode) -> str:
    return node.full_path.replace(" / ", " > ")


def _leaf_definition_text(node: TaxonomyNode) -> str:
    return node.definition.strip() or node.name


def _get_leaf_embedding_cards(
    leaf_nodes: list[TaxonomyNode],
    embedding_model: EmbeddingModel,
) -> list[_LeafEmbeddingCard]:
    cache_key = _leaf_embedding_cache_key(leaf_nodes, embedding_model)
    with _LEAF_EMBEDDING_CACHE_LOCK:
        cached = _LEAF_EMBEDDING_CACHE.get(cache_key)
        if cached is not None:
            return cached

    texts: list[str] = []
    for node in leaf_nodes:
        texts.append(_leaf_name_text(node))
        texts.append(_leaf_definition_text(node))

    embeddings = embedding_model.encode(texts=texts, text_type=EmbedTextType.PASSAGE)
    cards = [
        _LeafEmbeddingCard(
            node_id=node.id,
            name_embedding=embeddings[index * 2],
            definition_embedding=embeddings[index * 2 + 1],
        )
        for index, node in enumerate(leaf_nodes)
    ]

    with _LEAF_EMBEDDING_CACHE_LOCK:
        _LEAF_EMBEDDING_CACHE[cache_key] = cards
    return cards


def _cosine_similarity(left: Embedding, right: Embedding) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions must match for taxonomy matching")

    dot_product = sum(
        left_value * right_value for left_value, right_value in zip(left, right)
    )
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _leaf_confidence(name_score: float, definition_score: float) -> float:
    combined_score = (
        _NAME_SCORE_WEIGHT * name_score + _DEFINITION_SCORE_WEIGHT * definition_score
    )
    return max(name_score, combined_score)


def _basis(name_score: float, definition_score: float) -> str:
    if name_score >= definition_score:
        return "leaf path semantic similarity"
    return "leaf definition semantic similarity"


def _embedding_model_for_match(
    db_session: Session,
    embedding_model: EmbeddingModel | None,
) -> EmbeddingModel:
    if embedding_model is not None:
        return embedding_model

    search_settings = get_current_search_settings(db_session)
    return EmbeddingModel.from_db_model(
        search_settings=search_settings,
        server_host=MODEL_SERVER_HOST,
        server_port=MODEL_SERVER_PORT,
    )


def match_taxonomy_query(
    *,
    query: str,
    settings: Settings,
    apply_to: TaxonomySearchApplyTo,
    db_session: Session,
    manual_node_ids: list[str] | None = None,
    embedding_model: EmbeddingModel | None = None,
    query_embedding: Embedding | None = None,
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
        return _manual_taxonomy_decision(
            manual_node_ids=manual_node_ids,
            config=config,
            nodes_by_id=nodes_by_id,
            db_session=db_session,
            start=start,
        )

    if config.taxonomy_search_mode in (TaxonomySearchMode.OFF, TaxonomySearchMode.MANUAL_ONLY):
        return TaxonomySearchDecision(reason="automatic taxonomy matching disabled")

    leaf_nodes = [node for node in nodes if node.level == TaxonomyNodeLevel.LEAF]
    if not leaf_nodes:
        return TaxonomySearchDecision(reason="no active taxonomy leaf nodes")

    elapsed_ms = int((time.monotonic() - start) * 1000)
    if elapsed_ms > config.taxonomy_search_timeout_ms:
        return TaxonomySearchDecision(
            reason="taxonomy matching timed out",
            timed_out=True,
            elapsed_ms=elapsed_ms,
        )

    model = _embedding_model_for_match(db_session, embedding_model)
    if query_embedding is None:
        query_embedding = get_query_embedding(
            query, db_session=db_session, embedding_model=model
        )

    leaf_cards = _get_leaf_embedding_cards(leaf_nodes, model)

    scores: list[tuple[TaxonomyNode, float, float, float, str]] = []
    for card in leaf_cards:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if elapsed_ms > config.taxonomy_search_timeout_ms:
            return TaxonomySearchDecision(
                reason="taxonomy matching timed out",
                timed_out=True,
                elapsed_ms=elapsed_ms,
            )

        node = nodes_by_id[card.node_id]
        name_score = _cosine_similarity(query_embedding, card.name_embedding)
        definition_score = _cosine_similarity(query_embedding, card.definition_embedding)
        confidence = _leaf_confidence(name_score, definition_score)
        scores.append(
            (
                node,
                confidence,
                name_score,
                definition_score,
                _basis(name_score, definition_score),
            )
        )

    candidates = [
        _candidate_from_node(
            node,
            nodes_by_id,
            confidence,
            basis,
            name_score=name_score,
            definition_score=definition_score,
        )
        for node, confidence, name_score, definition_score, basis in sorted(
            scores, key=lambda item: item[1], reverse=True
        )[:_MAX_CANDIDATES]
    ]

    best = candidates[0] if candidates else None
    threshold = _threshold_for_leaf(config)
    if best is None or best.confidence < threshold:
        return TaxonomySearchDecision(
            candidates=candidates,
            reason="no leaf taxonomy candidate passed configured threshold",
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )

    leaf_ids = get_node_descendant_leaf_ids(
        db_session, node_ids=[best.node_id], active_only=True
    )
    if not leaf_ids:
        return TaxonomySearchDecision(
            candidates=candidates,
            reason="matched leaf node is not active",
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )

    if config.taxonomy_search_mode == TaxonomySearchMode.SUGGEST_ONLY:
        action = TaxonomySearchRecommendedAction.SUGGEST
    else:
        action = TaxonomySearchRecommendedAction.AUGMENT_SEARCH

    return TaxonomySearchDecision(
        matched=True,
        node_id=best.node_id,
        node_level=best.node_level,
        path=best.path,
        confidence=best.confidence,
        candidates=candidates,
        expanded_leaf_ids=leaf_ids[: config.taxonomy_search_max_leaf_expansion_count],
        recommended_action=action,
        reason="leaf semantic confidence passed threshold",
        elapsed_ms=int((time.monotonic() - start) * 1000),
    )
