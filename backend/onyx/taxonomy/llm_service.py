from __future__ import annotations

import json
from collections.abc import Iterator
from concurrent.futures import as_completed
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.enums import TaxonomyNodeSource
from onyx.db.enums import TaxonomyNodeStatus
from onyx.db.enums import TaxonomyTagSource
from onyx.db.models import TaxonomyNode
from onyx.db.taxonomy import validate_taxonomy_tree
from onyx.llm.constants import LlmProviderNames
from onyx.llm.factory import get_default_llm
from onyx.llm.interfaces import LLM
from onyx.llm.models import ReasoningEffort
from onyx.llm.models import UserMessage
from onyx.llm.utils import llm_response_to_string
from onyx.taxonomy.constants import TAXONOMY_PROMPT_VERSION
from onyx.taxonomy.models import TaxonomyDraftStreamEvent
from onyx.taxonomy.models import TaxonomyNodeCreate
from onyx.tracing.flows import LLMFlow
from onyx.tracing.llm_utils import llm_generation_span
from onyx.tracing.llm_utils import record_llm_response
from onyx.utils.logger import setup_logger

logger = setup_logger()

JSON_OBJECT_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}
JSON_OBJECT_RESPONSE_FORMAT_PROVIDERS = {
    LlmProviderNames.OPENAI,
    LlmProviderNames.AZURE,
}


@dataclass(frozen=True)
class TaxonomyTagRecommendation:
    leaf_node_id: str
    confidence: float
    evidence: str
    source: TaxonomyTagSource = TaxonomyTagSource.AI_RECOMMENDED


@dataclass(frozen=True)
class TaxonomyCandidateRecommendation:
    path: list[str]
    definition: str
    evidence: str
    confidence: float
    redundancy_result: str
    suggested_reuse_node_id: str | None = None


@dataclass(frozen=True)
class TaxonomyTaggingResult:
    tags: list[TaxonomyTagRecommendation]
    unmatched_reason: str | None
    candidates: list[TaxonomyCandidateRecommendation]


class TaxonomyJsonParseError(ValueError):
    pass


SYSTEM_TAXONOMY_QUALITY_CRITERIA = """
统一优化指标：
- 层级正确：固定 l1 -> l2 -> leaf，文档最终只能绑定 leaf。
- 语义不重复：同级标签不得高度重叠，跨分支标签边界要清晰。
- 粒度一致：同一层级的标签抽象程度要接近，避免一个极大一个极细。
- 可打标：leaf 必须能直接用于文章绑定，名称不应只是宽泛主题。
- 边界清楚：definition/applicability 要能区分相近标签。
- 覆盖合理：覆盖用户输入中的主要业务对象、流程、场景和异常。
- 命名统一：优先使用简洁名词短语，避免长句和混乱口径。
- 数量受控：leaf 总数不得超过给定预算。
"""


def _json_response_format_for_llm(llm: LLM) -> dict[str, str] | None:
    if llm.config.model_provider in JSON_OBJECT_RESPONSE_FORMAT_PROVIDERS:
        return JSON_OBJECT_RESPONSE_FORMAT
    return None


def _strip_json_markdown(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    return stripped


def _extract_json_object_text(raw: str) -> str:
    stripped = _strip_json_markdown(raw)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return stripped
    return stripped[start : end + 1]


def _extract_json(raw: str) -> dict[str, Any]:
    stripped = _strip_json_markdown(raw)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as first_error:
        extracted = _extract_json_object_text(stripped)
        if extracted == stripped:
            raise TaxonomyJsonParseError(str(first_error)) from first_error
        try:
            parsed = json.loads(extracted)
        except json.JSONDecodeError as second_error:
            raise TaxonomyJsonParseError(str(second_error)) from second_error
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object")
    return parsed


def _repair_json_with_llm(*, raw: str, llm: LLM) -> dict[str, Any]:
    json_text = _extract_json_object_text(raw)
    repair_prompt = f"""
你是 JSON 修复器。请修复下面内容中的 JSON 语法错误。

要求：
- 只输出一个合法 JSON 对象。
- 不要输出 Markdown。
- 不要解释。
- 不要新增、删除或改写业务语义，只修复引号、逗号、括号、数组和对象结构。

待修复内容：
{json_text}
"""
    prompt_msg = UserMessage(content=repair_prompt)
    with llm_generation_span(
        llm=llm,
        flow=LLMFlow.TAXONOMY_JSON_REPAIR,
        input_messages=[prompt_msg],
    ) as span_generation:
        response = llm.invoke(
            prompt_msg,
            structured_response_format=_json_response_format_for_llm(llm),
            max_tokens=max(1200, len(json_text) // 2),
            reasoning_effort=ReasoningEffort.OFF,
        )
        record_llm_response(span_generation, response)
    return _extract_json(llm_response_to_string(response))


def _invoke_json(
    *,
    llm: LLM,
    prompt: str,
    flow: LLMFlow,
    max_tokens: int = 1800,
) -> dict[str, Any]:
    prompt_msg = UserMessage(content=prompt)
    with llm_generation_span(
        llm=llm,
        flow=flow,
        input_messages=[prompt_msg],
    ) as span_generation:
        response = llm.invoke(
            prompt_msg,
            structured_response_format=_json_response_format_for_llm(llm),
            max_tokens=max_tokens,
            reasoning_effort=ReasoningEffort.OFF,
        )
        record_llm_response(span_generation, response)
    raw = llm_response_to_string(response)
    try:
        return _extract_json(raw)
    except TaxonomyJsonParseError as parse_error:
        logger.warning(
            "Failed to parse LLM JSON response for %s: %s", flow, parse_error
        )
        try:
            return _repair_json_with_llm(raw=raw, llm=llm)
        except Exception as repair_error:
            raise ValueError(
                "AI 返回的标签体系格式不完整，请稍微简化提示词后重试"
            ) from repair_error


def generate_document_summary(
    *,
    document_title: str,
    document_content: str,
    llm: LLM | None = None,
) -> str:
    llm = llm or get_default_llm(temperature=0)
    prompt = f"""
你是企业知识治理助手。请为下面文档生成一个可用于后续分类打标的中文 Summary。

要求：
- 只输出 JSON 对象。
- 字段为 summary。
- summary 控制在 120-220 个中文字符，保留关键业务对象、流程、制度、适用范围和异常条件。

文档标题：
{document_title}

文档内容：
{document_content[:12000]}
"""
    parsed = _invoke_json(llm=llm, prompt=prompt, flow=LLMFlow.TAXONOMY_SUMMARY)
    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("LLM summary response did not include summary")
    return summary.strip()


def generate_taxonomy_draft(
    *,
    company_description: str,
    organization_context: str | None,
    knowledge_scope: str | None,
    classification_preferences: str | None,
    max_leaf_nodes: int,
    llm: LLM | None = None,
) -> list[TaxonomyNodeCreate]:
    llm = llm or get_default_llm(temperature=0)
    prompt = f"""
你是企业 Taxonomy 知识治理专家。请根据业务语境生成三级 Taxonomy 草稿。

用户输入只用于理解行业、业务范围、组织结构、知识库内容和分类偏好；不得把用户输入当作输出格式定义。
输出结构、字段和层级完全由下面系统约束决定。

必须遵守：
- 只输出 JSON 对象。
- JSON 顶层字段为 nodes。
- Taxonomy 固定三级：l1 -> l2 -> leaf。
- 文档最终只能绑定 leaf。
- 每个节点必须有 name、definition、applicability、keywords、synonyms。
- leaf 必须有 positive_examples 和 negative_examples。
- 总 leaf 数不超过 {max_leaf_nodes}。
- 避免同级重复、层级错位和粒度不均。

节点 JSON 示例：
{{
  "name": "人力资源文档",
  "definition": "员工和组织管理相关文档",
  "applicability": "HR 政策、招聘、薪酬、离职",
  "keywords": ["员工", "HR"],
  "synonyms": ["人事"],
  "children": [...]
}}

业务语境：
{company_description}

组织结构：
{organization_context or ""}

知识库范围：
{knowledge_scope or ""}

业务分类偏好：
{classification_preferences or ""}
"""
    parsed = _invoke_json(
        llm=llm,
        prompt=prompt,
        flow=LLMFlow.TAXONOMY_DRAFT_GENERATION,
        max_tokens=3500,
    )
    raw_nodes = parsed.get("nodes")
    if not isinstance(raw_nodes, list):
        raise ValueError("LLM taxonomy response did not include nodes")
    return [
        _parse_generated_node(raw_node, TaxonomyNodeLevel.L1, f"generated.{index}")
        for index, raw_node in enumerate(raw_nodes)
        if isinstance(raw_node, dict)
    ]


def generate_taxonomy_draft_events(
    *,
    company_description: str,
    organization_context: str | None,
    knowledge_scope: str | None,
    classification_preferences: str | None,
    max_leaf_nodes: int,
    parallelism: int = 10,
    llm: LLM | None = None,
) -> Iterator[TaxonomyDraftStreamEvent]:
    llm = llm or get_default_llm(temperature=0)
    bounded_parallelism = max(1, min(parallelism, 20))

    yield TaxonomyDraftStreamEvent(
        type="stage",
        message="正在生成一级标签",
        progress=5,
    )
    l1_nodes, l1_leaf_budgets, l1_l2_targets = _generate_l1_nodes(
        llm=llm,
        company_description=company_description,
        organization_context=organization_context,
        knowledge_scope=knowledge_scope,
        classification_preferences=classification_preferences,
        max_leaf_nodes=max_leaf_nodes,
    )
    yield TaxonomyDraftStreamEvent(
        type="nodes",
        message="一级标签已生成，开始并行生成二级标签",
        nodes=_clone_nodes(l1_nodes),
        progress=12,
    )

    l2_leaf_budgets: dict[str, int] = {}
    l2_completed = 0
    with ThreadPoolExecutor(max_workers=min(bounded_parallelism, len(l1_nodes))) as pool:
        futures = {
            pool.submit(
                _generate_l2_nodes,
                llm=llm,
                company_description=company_description,
                organization_context=organization_context,
                knowledge_scope=knowledge_scope,
                classification_preferences=classification_preferences,
                all_l1_nodes=l1_nodes,
                l1_node=l1_node,
                target_l2_count=l1_l2_targets[l1_node.id or ""],
                leaf_budget=l1_leaf_budgets[l1_node.id or ""],
            ): l1_node
            for l1_node in l1_nodes
        }
        for future in as_completed(futures):
            l1_node = futures[future]
            l2_nodes, budgets = future.result()
            l1_node.children = l2_nodes
            l2_leaf_budgets.update(budgets)
            l2_completed += 1
            progress = 12 + round((l2_completed / max(1, len(futures))) * 30)
            yield TaxonomyDraftStreamEvent(
                type="nodes",
                message=f"已生成「{l1_node.name}」下的二级标签",
                nodes=_clone_nodes(l1_nodes),
                progress=progress,
            )

    l2_jobs: list[tuple[TaxonomyNodeCreate, TaxonomyNodeCreate, int]] = []
    for l1_node in l1_nodes:
        for l2_node in l1_node.children:
            l2_jobs.append(
                (l1_node, l2_node, l2_leaf_budgets.get(l2_node.id or "", 1))
            )

    yield TaxonomyDraftStreamEvent(
        type="stage",
        message="正在并行生成三级标签",
        nodes=_clone_nodes(l1_nodes),
        progress=45,
    )
    leaf_completed = 0
    with ThreadPoolExecutor(max_workers=min(bounded_parallelism, len(l2_jobs))) as pool:
        futures = {
            pool.submit(
                _generate_leaf_nodes,
                llm=llm,
                company_description=company_description,
                organization_context=organization_context,
                knowledge_scope=knowledge_scope,
                classification_preferences=classification_preferences,
                all_l1_nodes=l1_nodes,
                l1_node=l1_node,
                l2_node=l2_node,
                leaf_budget=leaf_budget,
            ): (l1_node, l2_node)
            for l1_node, l2_node, leaf_budget in l2_jobs
        }
        for future in as_completed(futures):
            _, l2_node = futures[future]
            l2_node.children = future.result()
            leaf_completed += 1
            progress = 45 + round((leaf_completed / max(1, len(futures))) * 40)
            yield TaxonomyDraftStreamEvent(
                type="nodes",
                message=f"已生成「{l2_node.name}」下的三级标签",
                nodes=_clone_nodes(l1_nodes),
                progress=progress,
            )

    validate_taxonomy_tree(l1_nodes)
    yield TaxonomyDraftStreamEvent(
        type="stage",
        message="正在按统一指标进行最终优化",
        nodes=_clone_nodes(l1_nodes),
        progress=92,
    )
    optimized_nodes = _optimize_taxonomy_draft(
        llm=llm,
        nodes=l1_nodes,
        company_description=company_description,
        organization_context=organization_context,
        knowledge_scope=knowledge_scope,
        classification_preferences=classification_preferences,
        max_leaf_nodes=max_leaf_nodes,
    )
    yield TaxonomyDraftStreamEvent(
        type="final",
        message="标签体系已完成最终优化",
        nodes=_clone_nodes(optimized_nodes),
        progress=100,
    )


def _generate_l1_nodes(
    *,
    llm: LLM,
    company_description: str,
    organization_context: str | None,
    knowledge_scope: str | None,
    classification_preferences: str | None,
    max_leaf_nodes: int,
) -> tuple[list[TaxonomyNodeCreate], dict[str, int], dict[str, int]]:
    prompt = f"""
你是企业 Taxonomy 知识治理专家。请先生成一级标签大纲。

必须遵守：
- 只输出 JSON 对象。
- JSON 顶层字段为 nodes。
- 只生成一级标签，不要输出 children。
- 每个一级标签必须包含 name、definition、applicability、keywords、synonyms。
- 每个一级标签必须包含 target_l2_count 和 target_leaf_count。
- target_leaf_count 合计不得超过 {max_leaf_nodes}。
- 一级标签之间边界清晰，避免语义重复。

{SYSTEM_TAXONOMY_QUALITY_CRITERIA}

业务语境：
{company_description}

组织结构：
{organization_context or ""}

知识库范围：
{knowledge_scope or ""}

业务分类偏好：
{classification_preferences or ""}
"""
    parsed = _invoke_json(
        llm=llm,
        prompt=prompt,
        flow=LLMFlow.TAXONOMY_LAYERED_DRAFT_GENERATION,
        max_tokens=1800,
    )
    raw_nodes = _require_raw_nodes(parsed)
    if len(raw_nodes) > max_leaf_nodes:
        raw_nodes = raw_nodes[:max_leaf_nodes]

    nodes: list[TaxonomyNodeCreate] = []
    raw_leaf_budgets: list[int] = []
    raw_l2_targets: list[int] = []
    for index, raw_node in enumerate(raw_nodes):
        if not isinstance(raw_node, dict):
            continue
        nodes.append(
            _parse_generated_node_shallow(
                raw_node,
                TaxonomyNodeLevel.L1,
                f"generated.l1.{index}",
            )
        )
        raw_leaf_budgets.append(_coerce_positive_int(raw_node.get("target_leaf_count")))
        raw_l2_targets.append(_coerce_positive_int(raw_node.get("target_l2_count")))
    if not nodes:
        raise ValueError("LLM taxonomy response did not include usable l1 nodes")

    leaf_budgets = _normalize_budgets(raw_leaf_budgets, max_leaf_nodes)
    l2_targets = [
        max(1, min(raw_l2_targets[index] or leaf_budgets[index], leaf_budgets[index]))
        for index in range(len(nodes))
    ]
    return (
        nodes,
        {nodes[index].id or "": leaf_budgets[index] for index in range(len(nodes))},
        {nodes[index].id or "": l2_targets[index] for index in range(len(nodes))},
    )


def _generate_l2_nodes(
    *,
    llm: LLM,
    company_description: str,
    organization_context: str | None,
    knowledge_scope: str | None,
    classification_preferences: str | None,
    all_l1_nodes: list[TaxonomyNodeCreate],
    l1_node: TaxonomyNodeCreate,
    target_l2_count: int,
    leaf_budget: int,
) -> tuple[list[TaxonomyNodeCreate], dict[str, int]]:
    prompt = f"""
你是企业 Taxonomy 知识治理专家。请为指定一级标签生成二级标签。

必须遵守：
- 只输出 JSON 对象。
- JSON 顶层字段为 nodes。
- 只生成二级标签，不要输出 children。
- 每个二级标签必须包含 name、definition、applicability、keywords、synonyms、target_leaf_count。
- 二级标签数量建议为 {target_l2_count} 个。
- target_leaf_count 合计不得超过 {leaf_budget}。
- 二级标签必须属于当前一级标签，且和同一体系内其他一级标签边界清楚。

{SYSTEM_TAXONOMY_QUALITY_CRITERIA}

全部一级标签：
{_nodes_context_for_prompt(all_l1_nodes)}

当前一级标签：
{_node_context_for_prompt(l1_node)}

业务语境：
{company_description}

组织结构：
{organization_context or ""}

知识库范围：
{knowledge_scope or ""}

业务分类偏好：
{classification_preferences or ""}
"""
    parsed = _invoke_json(
        llm=llm,
        prompt=prompt,
        flow=LLMFlow.TAXONOMY_LAYERED_DRAFT_GENERATION,
        max_tokens=1800,
    )
    raw_nodes = _require_raw_nodes(parsed)[:leaf_budget]
    nodes: list[TaxonomyNodeCreate] = []
    raw_leaf_budgets: list[int] = []
    for index, raw_node in enumerate(raw_nodes):
        if not isinstance(raw_node, dict):
            continue
        nodes.append(
            _parse_generated_node_shallow(
                raw_node,
                TaxonomyNodeLevel.L2,
                f"{l1_node.id}.l2.{index}",
            )
        )
        raw_leaf_budgets.append(_coerce_positive_int(raw_node.get("target_leaf_count")))
    if not nodes:
        raise ValueError(f"LLM did not generate l2 nodes for {l1_node.name}")

    leaf_budgets = _normalize_budgets(raw_leaf_budgets, leaf_budget)
    return (
        nodes,
        {nodes[index].id or "": leaf_budgets[index] for index in range(len(nodes))},
    )


def _generate_leaf_nodes(
    *,
    llm: LLM,
    company_description: str,
    organization_context: str | None,
    knowledge_scope: str | None,
    classification_preferences: str | None,
    all_l1_nodes: list[TaxonomyNodeCreate],
    l1_node: TaxonomyNodeCreate,
    l2_node: TaxonomyNodeCreate,
    leaf_budget: int,
) -> list[TaxonomyNodeCreate]:
    prompt = f"""
你是企业 Taxonomy 知识治理专家。请为指定二级标签生成可直接绑定文章的三级 leaf 标签。

必须遵守：
- 只输出 JSON 对象。
- JSON 顶层字段为 nodes。
- 只生成 leaf 标签，不要输出 children。
- leaf 数量不得超过 {leaf_budget}。
- 每个 leaf 必须包含 name、definition、applicability、keywords、synonyms、positive_examples、negative_examples。
- leaf 必须可直接用于文章绑定，不能只是宽泛主题。
- 同一二级标签下 leaf 不得重复，且要和同一一级下其他二级标签边界清楚。

{SYSTEM_TAXONOMY_QUALITY_CRITERIA}

全部一级标签：
{_nodes_context_for_prompt(all_l1_nodes)}

当前一级标签：
{_node_context_for_prompt(l1_node)}

当前一级下已有二级标签：
{_nodes_context_for_prompt(l1_node.children)}

当前二级标签：
{_node_context_for_prompt(l2_node)}

业务语境：
{company_description}

组织结构：
{organization_context or ""}

知识库范围：
{knowledge_scope or ""}

业务分类偏好：
{classification_preferences or ""}
"""
    parsed = _invoke_json(
        llm=llm,
        prompt=prompt,
        flow=LLMFlow.TAXONOMY_LAYERED_DRAFT_GENERATION,
        max_tokens=max(2200, leaf_budget * 220),
    )
    raw_nodes = _require_raw_nodes(parsed)[:leaf_budget]
    nodes = [
        _parse_generated_node_shallow(
            raw_node,
            TaxonomyNodeLevel.LEAF,
            f"{l2_node.id}.leaf.{index}",
        )
        for index, raw_node in enumerate(raw_nodes)
        if isinstance(raw_node, dict)
    ]
    if not nodes:
        raise ValueError(f"LLM did not generate leaf nodes for {l2_node.name}")
    return nodes


def _optimize_taxonomy_draft(
    *,
    llm: LLM,
    nodes: list[TaxonomyNodeCreate],
    company_description: str,
    organization_context: str | None,
    knowledge_scope: str | None,
    classification_preferences: str | None,
    max_leaf_nodes: int,
) -> list[TaxonomyNodeCreate]:
    prompt = f"""
你是企业 Taxonomy 全局审稿 Agent。请对输入的三级标签体系做最终优化。

重要限制：
- 不要从零重写，必须基于输入树优化。
- 允许合并重复、改名、调整层级边界、补齐说明和例子。
- 不允许改变三级结构，必须保持 l1 -> l2 -> leaf。
- leaf 总数不得超过 {max_leaf_nodes}。
- 每个节点必须包含 name、definition、applicability、keywords、synonyms。
- 每个 leaf 必须包含 positive_examples、negative_examples。
- 只输出 JSON 对象，不要解释。
- 顶层字段为 nodes 和 change_summary。

{SYSTEM_TAXONOMY_QUALITY_CRITERIA}

业务语境：
{company_description}

组织结构：
{organization_context or ""}

知识库范围：
{knowledge_scope or ""}

业务分类偏好：
{classification_preferences or ""}

待优化标签树：
{_nodes_json_for_prompt(nodes)}
"""
    try:
        parsed = _invoke_json(
            llm=llm,
            prompt=prompt,
            flow=LLMFlow.TAXONOMY_DRAFT_OPTIMIZATION,
            max_tokens=max(4500, max_leaf_nodes * 220),
        )
        raw_nodes = _require_raw_nodes(parsed)
        optimized_nodes = [
            _parse_generated_node(raw_node, TaxonomyNodeLevel.L1, f"optimized.{index}")
            for index, raw_node in enumerate(raw_nodes)
            if isinstance(raw_node, dict)
        ]
        validate_taxonomy_tree(optimized_nodes)
        if _count_leaf_nodes(optimized_nodes) > max_leaf_nodes:
            raise ValueError("Optimized taxonomy exceeded leaf budget")
        return optimized_nodes
    except Exception as e:
        logger.warning("Failed taxonomy draft optimization; using generated tree: %s", e)
        return nodes


def _require_raw_nodes(parsed: dict[str, Any]) -> list[Any]:
    raw_nodes = parsed.get("nodes")
    if not isinstance(raw_nodes, list):
        raise ValueError("LLM taxonomy response did not include nodes")
    return raw_nodes


def _parse_generated_node_shallow(
    raw_node: dict[str, Any],
    level: TaxonomyNodeLevel,
    prefix: str,
) -> TaxonomyNodeCreate:
    return _parse_generated_node(
        {**raw_node, "children": []},
        level,
        prefix,
    )


def _clone_nodes(nodes: list[TaxonomyNodeCreate]) -> list[TaxonomyNodeCreate]:
    return [node.model_copy(deep=True) for node in nodes]


def _coerce_positive_int(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 0
    return max(0, value)


def _normalize_budgets(raw_budgets: list[int], max_total: int) -> list[int]:
    if not raw_budgets:
        return []
    budgets = [max(1, budget) for budget in raw_budgets]
    while sum(budgets) > max_total and any(budget > 1 for budget in budgets):
        largest_index = max(range(len(budgets)), key=lambda index: budgets[index])
        budgets[largest_index] -= 1
    index = 0
    while sum(budgets) < max_total:
        budgets[index % len(budgets)] += 1
        index += 1
    return budgets


def _nodes_context_for_prompt(nodes: list[TaxonomyNodeCreate]) -> str:
    return "\n".join(_node_context_for_prompt(node) for node in nodes)


def _node_context_for_prompt(node: TaxonomyNodeCreate) -> str:
    return (
        f"- id: {node.id}\n"
        f"  level: {node.level.value}\n"
        f"  name: {node.name}\n"
        f"  definition: {node.definition}\n"
        f"  applicability: {node.applicability}\n"
        f"  keywords: {', '.join(node.keywords)}\n"
        f"  synonyms: {', '.join(node.synonyms)}"
    )


def _nodes_json_for_prompt(nodes: list[TaxonomyNodeCreate]) -> str:
    return json.dumps(
        [node.model_dump(mode="json") for node in nodes],
        ensure_ascii=False,
        indent=2,
    )


def _count_leaf_nodes(nodes: list[TaxonomyNodeCreate]) -> int:
    count = 0
    for node in nodes:
        if node.level == TaxonomyNodeLevel.LEAF:
            count += 1
        count += _count_leaf_nodes(node.children)
    return count


def _parse_generated_node(
    raw_node: dict[str, Any],
    level: TaxonomyNodeLevel,
    prefix: str,
) -> TaxonomyNodeCreate:
    raw_children = raw_node.get("children") or []
    next_level = (
        TaxonomyNodeLevel.L2
        if level == TaxonomyNodeLevel.L1
        else TaxonomyNodeLevel.LEAF
    )
    children = (
        [
            _parse_generated_node(child, next_level, f"{prefix}.{child_index}")
            for child_index, child in enumerate(raw_children)
            if isinstance(child, dict)
        ]
        if level != TaxonomyNodeLevel.LEAF
        else []
    )
    name = str(raw_node.get("name") or "未命名分类").strip()
    return TaxonomyNodeCreate(
        id=prefix,
        level=level,
        name=name,
        definition=str(raw_node.get("definition") or name).strip(),
        applicability=str(raw_node.get("applicability") or "").strip(),
        positive_examples=[
            str(item).strip()
            for item in raw_node.get("positive_examples", [])
            if str(item).strip()
        ],
        negative_examples=[
            str(item).strip()
            for item in raw_node.get("negative_examples", [])
            if str(item).strip()
        ],
        keywords=[
            str(item).strip()
            for item in raw_node.get("keywords", [])
            if str(item).strip()
        ],
        synonyms=[
            str(item).strip()
            for item in raw_node.get("synonyms", [])
            if str(item).strip()
        ],
        tagging_guidance=raw_node.get("tagging_guidance"),
        source=TaxonomyNodeSource.AI_GENERATED,
        status=TaxonomyNodeStatus.DRAFT,
        children=children,
    )


def recommend_taxonomy_tags(
    *,
    document_title: str,
    document_content: str,
    leaf_nodes: list[TaxonomyNode],
    enable_optimization: bool,
    llm: LLM | None = None,
) -> TaxonomyTaggingResult:
    if not leaf_nodes:
        raise ValueError("Cannot tag documents without active leaf nodes")
    llm = llm or get_default_llm(temperature=0)
    leaf_cards = "\n".join(
        f"- id: {node.id}\n  path: {node.full_path}\n  definition: {node.definition}\n"
        f"  keywords: {', '.join(node.keywords or [])}\n"
        f"  synonyms: {', '.join(node.synonyms or [])}\n"
        f"  positive: {', '.join(node.positive_examples or [])}\n"
        f"  negative: {', '.join(node.negative_examples or [])}"
        for node in leaf_nodes
    )
    prompt = f"""
你是企业知识库打标 Agent。请基于当前生效 Taxonomy 为文档推荐 leaf 标签。

必须遵守：
- 只输出 JSON 对象。
- 只能从候选 leaf id 中选择标签。
- 可多标签，但通常选择 1-3 个最相关 leaf。
- confidence 为 0 到 1。
- 若无法覆盖，写 unmatched_reason。
- enable_optimization={str(enable_optimization).lower()}。只有为 true 时，才允许输出 candidates。
- candidates 必须是完整三级路径，字段 path 为长度 3 的数组。

输出 JSON 结构：
{{
  "tags": [{{"leaf_node_id": "...", "confidence": 0.91, "evidence": "..."}}],
  "unmatched_reason": null,
  "candidates": [
    {{
      "path": ["一级", "二级", "三级"],
      "definition": "...",
      "evidence": "...",
      "confidence": 0.82,
      "redundancy_result": "not_redundant|reuse_existing|needs_handling",
      "suggested_reuse_node_id": null
    }}
  ]
}}

候选 leaf：
{leaf_cards}

文档标题：
{document_title}

打标输入：
{document_content[:12000]}
"""
    parsed = _invoke_json(
        llm=llm,
        prompt=prompt,
        flow=LLMFlow.TAXONOMY_TAGGING,
        max_tokens=2500,
    )
    valid_leaf_ids = {node.id for node in leaf_nodes}
    tags: list[TaxonomyTagRecommendation] = []
    for raw_tag in parsed.get("tags", []):
        if not isinstance(raw_tag, dict):
            continue
        leaf_id = raw_tag.get("leaf_node_id")
        if not isinstance(leaf_id, str) or leaf_id not in valid_leaf_ids:
            continue
        confidence = _coerce_confidence(raw_tag.get("confidence"))
        tags.append(
            TaxonomyTagRecommendation(
                leaf_node_id=leaf_id,
                confidence=confidence,
                evidence=str(raw_tag.get("evidence") or ""),
            )
        )

    candidates: list[TaxonomyCandidateRecommendation] = []
    if enable_optimization:
        for raw_candidate in parsed.get("candidates", []):
            if not isinstance(raw_candidate, dict):
                continue
            raw_path = raw_candidate.get("path")
            if not isinstance(raw_path, list) or len(raw_path) != 3:
                continue
            candidates.append(
                TaxonomyCandidateRecommendation(
                    path=[str(part).strip() for part in raw_path],
                    definition=str(raw_candidate.get("definition") or "").strip(),
                    evidence=str(raw_candidate.get("evidence") or "").strip(),
                    confidence=_coerce_confidence(raw_candidate.get("confidence")),
                    redundancy_result=str(
                        raw_candidate.get("redundancy_result") or "needs_handling"
                    ),
                    suggested_reuse_node_id=raw_candidate.get(
                        "suggested_reuse_node_id"
                    ),
                )
            )

    unmatched_reason = parsed.get("unmatched_reason")
    return TaxonomyTaggingResult(
        tags=tags,
        unmatched_reason=unmatched_reason
        if isinstance(unmatched_reason, str)
        else None,
        candidates=candidates,
    )


def _coerce_confidence(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, min(1.0, value))


def model_info(llm: LLM) -> dict[str, str]:
    return {
        "model_provider": llm.config.model_provider,
        "model_name": llm.config.model_name,
        "prompt_version": TAXONOMY_PROMPT_VERSION,
    }
