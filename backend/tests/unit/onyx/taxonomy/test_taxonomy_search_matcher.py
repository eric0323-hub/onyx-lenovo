from __future__ import annotations

from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.taxonomy import build_health_summary
from onyx.db.taxonomy import validate_taxonomy_tree
from onyx.server.settings.models import Settings
from onyx.taxonomy.default_template import get_default_taxonomy_template
from onyx.taxonomy.models import TaxonomySearchApplyTo
from onyx.taxonomy.models import TaxonomySearchMode
from onyx.taxonomy.search_matcher import match_taxonomy_query


class StubNode:
    def __init__(
        self,
        *,
        id: str,
        level: TaxonomyNodeLevel,
        name: str,
        full_path: str,
        path_node_ids: list[str],
        parent_id: str | None = None,
        keywords: list[str] | None = None,
        synonyms: list[str] | None = None,
        definition: str = "",
    ) -> None:
        self.id = id
        self.level = level
        self.name = name
        self.display_name = None
        self.full_path = full_path
        self.path_node_ids = path_node_ids
        self.parent_id = parent_id
        self.keywords = keywords or []
        self.synonyms = synonyms or []
        self.definition = definition
        self.applicability = ""
        self.positive_examples = []
        self.negative_examples = []


def test_default_template_is_valid_three_level_tree() -> None:
    nodes = get_default_taxonomy_template()

    validate_taxonomy_tree(nodes)
    health_summary = build_health_summary(nodes)

    assert health_summary["l1_count"] > 0
    assert health_summary["l2_count"] > 0
    assert health_summary["leaf_count"] > 0
    assert health_summary["duplicate_names"] == []
    assert health_summary["leaf_nodes_missing_examples"] == []


def test_matcher_returns_disabled_when_taxonomy_search_is_off() -> None:
    decision = match_taxonomy_query(
        query="假期政策",
        settings=Settings(taxonomy_search_enabled=False),
        apply_to=TaxonomySearchApplyTo.SEARCH,
        db_session=None,  # type: ignore[arg-type]
    )

    assert decision.matched is False
    assert decision.reason == "taxonomy search disabled"


def test_matcher_matches_leaf_and_expands_to_leaf_ids(monkeypatch) -> None:
    nodes = [
        StubNode(
            id="v1.hr",
            level=TaxonomyNodeLevel.L1,
            name="人力资源文档",
            full_path="人力资源文档",
            path_node_ids=["v1.hr"],
        ),
        StubNode(
            id="v1.hr.policy",
            level=TaxonomyNodeLevel.L2,
            name="HR 政策",
            full_path="人力资源文档 / HR 政策",
            path_node_ids=["v1.hr", "v1.hr.policy"],
            parent_id="v1.hr",
        ),
        StubNode(
            id="v1.hr.policy.leave",
            level=TaxonomyNodeLevel.LEAF,
            name="假期政策",
            full_path="人力资源文档 / HR 政策 / 假期政策",
            path_node_ids=["v1.hr", "v1.hr.policy", "v1.hr.policy.leave"],
            parent_id="v1.hr.policy",
            keywords=["年假", "请假"],
            synonyms=["休假制度"],
            definition="员工假期、年假、请假流程相关文档。",
        ),
    ]

    monkeypatch.setattr(
        "onyx.taxonomy.search_matcher.get_active_nodes", lambda _: nodes
    )
    monkeypatch.setattr(
        "onyx.taxonomy.search_matcher.get_node_descendant_leaf_ids",
        lambda *_, **__: ["v1.hr.policy.leave"],
    )

    decision = match_taxonomy_query(
        query="员工年假和请假流程",
        settings=Settings(
            taxonomy_search_enabled=True,
            taxonomy_search_mode=TaxonomySearchMode.SOFT_FILTER_WITH_FALLBACK,
            taxonomy_search_apply_to=TaxonomySearchApplyTo.SEARCH,
            taxonomy_search_default_confidence_threshold=0.3,
        ),
        apply_to=TaxonomySearchApplyTo.SEARCH,
        db_session=None,  # type: ignore[arg-type]
    )

    assert decision.matched is True
    assert decision.node_id == "v1.hr.policy.leave"
    assert decision.path == ["人力资源文档", "HR 政策", "假期政策"]
    assert decision.expanded_leaf_ids == ["v1.hr.policy.leave"]
    assert decision.recommended_action.value == "soft_filter"
