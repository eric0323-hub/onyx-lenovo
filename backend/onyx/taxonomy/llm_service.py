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
from onyx.taxonomy.models import DEFAULT_TAXONOMY_L1_L2_PROMPT_TEMPLATE
from onyx.taxonomy.models import DEFAULT_TAXONOMY_LEAF_PROMPT_TEMPLATE
from onyx.taxonomy.models import TaxonomyDraftStreamEvent
from onyx.taxonomy.models import TaxonomyGenerationRuntimeConfig
from onyx.taxonomy.models import TaxonomyNodeCreate
from onyx.tracing.flows import LLMFlow
from onyx.tracing.llm_utils import llm_generation_span
from onyx.tracing.llm_utils import record_llm_response
from onyx.utils.logger import setup_logger

logger = setup_logger()

JSON_OBJECT_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}
JSON_OBJECT_RESPONSE_FORMAT_PROVIDERS: set[str] = {
    LlmProviderNames.OPENAI.value,
    LlmProviderNames.AZURE.value,
    "volcengine",
    "deepseek",
}
JSON_OBJECT_RESPONSE_FORMAT_DEEPSEEK_PROXY_PROVIDERS: set[str] = {
    LlmProviderNames.OPENROUTER.value,
    LlmProviderNames.OPENAI_COMPATIBLE.value,
    LlmProviderNames.LITELLM_PROXY.value,
}
DEEPSEEK_TAXONOMY_MIN_OUTPUT_TOKENS = 8000
DISABLE_THINKING_EXTRA_BODY: dict[str, bool] = {"enable_thinking": False}


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


@dataclass(frozen=True)
class TaxonomyExistingLabelFallbackResult:
    tags: list[TaxonomyTagRecommendation]
    reason: str


@dataclass(frozen=True)
class TaxonomyCandidateForHealthCheck:
    candidate_id: int
    document_id: str
    path: list[str]
    definition: str
    evidence: str
    confidence: float


@dataclass(frozen=True)
class TaxonomyCandidateHealthDecision:
    candidate_id: int
    action: str
    reason: str
    suggested_reuse_node_id: str | None = None
    parent_l2_node_id: str | None = None
    leaf_name: str | None = None
    definition: str | None = None
    applicability: str | None = None
    keywords: list[str] | None = None
    synonyms: list[str] | None = None
    positive_examples: list[str] | None = None
    negative_examples: list[str] | None = None


class TaxonomyJsonParseError(ValueError):
    pass


TAXONOMY_HEALTH_DECISION_ACTIONS = {
    "reuse_existing",
    "add_leaf",
    "reject",
    "needs_handling",
}

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
    if (
        llm.config.model_provider in JSON_OBJECT_RESPONSE_FORMAT_DEEPSEEK_PROXY_PROVIDERS
        and "deepseek" in llm.config.model_name.lower()
    ):
        return JSON_OBJECT_RESPONSE_FORMAT
    return None


def _is_deepseek_llm(llm: LLM) -> bool:
    return llm.config.model_provider == "deepseek" or (
        llm.config.model_provider in JSON_OBJECT_RESPONSE_FORMAT_DEEPSEEK_PROXY_PROVIDERS
        and "deepseek" in llm.config.model_name.lower()
    )


def _taxonomy_json_max_tokens_for_llm(*, llm: LLM, max_tokens: int) -> int:
    if _is_deepseek_llm(llm):
        return max(max_tokens, DEEPSEEK_TAXONOMY_MIN_OUTPUT_TOKENS)
    return max_tokens


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
            extra_body=DISABLE_THINKING_EXTRA_BODY,
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
            max_tokens=_taxonomy_json_max_tokens_for_llm(
                llm=llm,
                max_tokens=max_tokens,
            ),
            reasoning_effort=ReasoningEffort.OFF,
            extra_body=DISABLE_THINKING_EXTRA_BODY,
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
    max_leaf_nodes: int | None = None,
    generation_config: TaxonomyGenerationRuntimeConfig | None = None,
    llm: LLM | None = None,
) -> list[TaxonomyNodeCreate]:
    final_nodes: list[TaxonomyNodeCreate] | None = None
    for event in generate_taxonomy_draft_events(
        company_description=company_description,
        organization_context=organization_context,
        knowledge_scope=knowledge_scope,
        classification_preferences=classification_preferences,
        max_leaf_nodes=max_leaf_nodes,
        generation_config=generation_config,
        llm=llm,
    ):
        if event.type == "final" and event.nodes is not None:
            final_nodes = event.nodes
    if final_nodes is None:
        raise ValueError("LLM taxonomy generation did not return final nodes")
    return final_nodes


def generate_taxonomy_draft_events(
    *,
    company_description: str,
    organization_context: str | None,
    knowledge_scope: str | None,
    classification_preferences: str | None,
    max_leaf_nodes: int | None,
    parallelism: int | None = None,
    generation_config: TaxonomyGenerationRuntimeConfig | None = None,
    llm: LLM | None = None,
) -> Iterator[TaxonomyDraftStreamEvent]:
    llm = llm or get_default_llm(temperature=0)
    generation_config = generation_config or TaxonomyGenerationRuntimeConfig(
        l1_l2_system_prompt=DEFAULT_TAXONOMY_L1_L2_PROMPT_TEMPLATE,
        leaf_system_prompt=DEFAULT_TAXONOMY_LEAF_PROMPT_TEMPLATE,
    )
    max_l1_l2_count = max_leaf_nodes or generation_config.first_level_max_count
    leaf_parallelism = parallelism or generation_config.third_level_parallelism
    bounded_leaf_parallelism = max(1, min(leaf_parallelism, 20))

    yield TaxonomyDraftStreamEvent(
        type="stage",
        message="正在发散、筛选并聚类一级/二级标签",
        progress=5,
    )
    l1_nodes = _generate_l1_l2_nodes(
        llm=llm,
        company_description=company_description,
        organization_context=organization_context,
        knowledge_scope=knowledge_scope,
        classification_preferences=classification_preferences,
        generation_config=generation_config,
        max_l1_l2_count=max_l1_l2_count,
    )
    yield TaxonomyDraftStreamEvent(
        type="nodes",
        message="一级/二级标签已完成 MECE 收敛，开始并行生成三级标签",
        nodes=_clone_nodes(l1_nodes),
        progress=30,
    )

    l2_jobs: list[tuple[TaxonomyNodeCreate, TaxonomyNodeCreate]] = []
    for l1_node in l1_nodes:
        for l2_node in l1_node.children:
            l2_jobs.append((l1_node, l2_node))

    yield TaxonomyDraftStreamEvent(
        type="stage",
        message="正在并行生成三级标签",
        nodes=_clone_nodes(l1_nodes),
        progress=35,
    )
    leaf_completed = 0
    with ThreadPoolExecutor(
        max_workers=min(bounded_leaf_parallelism, max(1, len(l2_jobs)))
    ) as pool:
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
                generation_config=generation_config,
            ): (l1_node, l2_node)
            for l1_node, l2_node in l2_jobs
        }
        for future in as_completed(futures):
            _, l2_node = futures[future]
            l2_node.children = future.result()
            leaf_completed += 1
            progress = 35 + round((leaf_completed / max(1, len(futures))) * 50)
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
        generation_config=generation_config,
    )
    yield TaxonomyDraftStreamEvent(
        type="final",
        message="标签体系已完成最终优化",
        nodes=_clone_nodes(optimized_nodes),
        progress=100,
    )


def _generate_l1_l2_nodes(
    *,
    llm: LLM,
    company_description: str,
    organization_context: str | None,
    knowledge_scope: str | None,
    classification_preferences: str | None,
    generation_config: TaxonomyGenerationRuntimeConfig,
    max_l1_l2_count: int,
) -> list[TaxonomyNodeCreate]:
    system_prompt = generation_config.l1_l2_system_prompt.strip()
    prompt = f"""
你是企业 Taxonomy 知识治理专家。请一次性生成一级/二级标签树。

系统提示词：
{system_prompt}

必须遵守：
- 只输出 JSON 对象。
- JSON 顶层字段为 nodes。
- Taxonomy 固定三级，但本步骤只输出 l1 -> l2，不要输出 leaf。
- 每个一级/二级标签必须包含 name、definition、applicability、keywords、synonyms。
- 每个一级标签必须有至少一个二级标签。
- 标签名称保持 2-6 个中文字符，专业、简洁、有区分度。
- 一级标签必须是互斥的顶级维度；二级标签必须属于对应一级标签且同级边界清楚。
- 最终 nodes 中一级标签和二级标签的总数量不得超过 {max_l1_l2_count}。

{SYSTEM_TAXONOMY_QUALITY_CRITERIA}

输出 JSON 结构：
{{
  "nodes": [
    {{
      "name": "业务流程",
      "definition": "业务流程相关知识",
      "applicability": "制度、审批、执行流程",
      "keywords": ["流程"],
      "synonyms": ["业务规范"],
      "children": [
        {{
          "name": "审批管理",
          "definition": "审批规则、流程节点和权限要求",
          "applicability": "审批制度、流程说明、异常处理",
          "keywords": ["审批"],
          "synonyms": ["流程审批"]
        }}
      ]
    }}
  ],
  "cluster_summary": ["可选：聚类名称或聚类依据"],
  "mece_summary": "可选：说明如何保证互斥和穷尽"
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
        flow=LLMFlow.TAXONOMY_LAYERED_DRAFT_GENERATION,
        max_tokens=max(3000, max_l1_l2_count * 260),
    )
    raw_nodes = _require_raw_nodes(parsed)
    nodes: list[TaxonomyNodeCreate] = []
    for index, raw_node in enumerate(raw_nodes):
        if not isinstance(raw_node, dict):
            continue
        nodes.append(_parse_l1_l2_generated_node(raw_node, f"generated.l1.{index}"))

    nodes = _limit_l1_l2_nodes(nodes, max_l1_l2_count)
    if not nodes:
        raise ValueError("LLM taxonomy response did not include usable l1/l2 nodes")
    return nodes


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
    generation_config: TaxonomyGenerationRuntimeConfig,
) -> list[TaxonomyNodeCreate]:
    leaf_budget = generation_config.third_level_max_count
    system_prompt = generation_config.leaf_system_prompt.strip()
    prompt = f"""
你是企业 Taxonomy 知识治理专家。请为指定二级标签生成可直接绑定文章的三级 leaf 标签。

系统提示词：
{system_prompt}

必须遵守：
- 只输出 JSON 对象。
- JSON 顶层字段为 nodes。
- 只生成 leaf 标签，不要输出 children。
- leaf 数量不得超过 {leaf_budget}。
- 每个 leaf 必须包含 name、definition、applicability、keywords、synonyms、positive_examples、negative_examples。
- leaf 必须可直接用于文章绑定，不能只是宽泛主题。
- 标签名称保持 2-6 个中文字符，专业、简洁、有区分度。
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
    generation_config: TaxonomyGenerationRuntimeConfig,
) -> list[TaxonomyNodeCreate]:
    l1_l2_system_prompt = generation_config.l1_l2_system_prompt.strip()
    leaf_system_prompt = generation_config.leaf_system_prompt.strip()
    prompt = f"""
你是企业 Taxonomy 全局审稿 Agent。请对输入的三级标签体系做最终优化。

一级/二级生成提示词：
{l1_l2_system_prompt}

三级标签生成提示词：
{leaf_system_prompt}

重要限制：
- 不要从零重写，必须基于输入树优化。
- 允许合并重复、改名、调整层级边界、补齐说明和例子。
- 不允许改变三级结构，必须保持 l1 -> l2 -> leaf。
- 一级标签 + 二级标签总数不得超过 {generation_config.first_level_max_count}。
- 每个二级标签下的 leaf 数量不得超过 {generation_config.third_level_max_count}。
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
            max_tokens=max(4500, _count_leaf_nodes(nodes) * 220),
        )
        raw_nodes = _require_raw_nodes(parsed)
        optimized_nodes = [
            _parse_generated_node(raw_node, TaxonomyNodeLevel.L1, f"optimized.{index}")
            for index, raw_node in enumerate(raw_nodes)
            if isinstance(raw_node, dict)
        ]
        optimized_nodes = _limit_taxonomy_tree_to_generation_config(
            optimized_nodes,
            generation_config,
        )
        validate_taxonomy_tree(optimized_nodes)
        if _leaf_count_exceeds_generation_config(optimized_nodes, generation_config):
            raise ValueError("Optimized taxonomy exceeded configured leaf budget")
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


def _parse_l1_l2_generated_node(
    raw_node: dict[str, Any],
    prefix: str,
) -> TaxonomyNodeCreate:
    node = _parse_generated_node_shallow(raw_node, TaxonomyNodeLevel.L1, prefix)
    raw_children = raw_node.get("children") or []
    node.children = [
        _parse_generated_node_shallow(
            child,
            TaxonomyNodeLevel.L2,
            f"{prefix}.l2.{child_index}",
        )
        for child_index, child in enumerate(raw_children)
        if isinstance(child, dict)
    ]
    return node


def _count_l1_l2_nodes(nodes: list[TaxonomyNodeCreate]) -> int:
    return sum(1 + len(node.children) for node in nodes)


def _limit_l1_l2_nodes(
    nodes: list[TaxonomyNodeCreate],
    max_l1_l2_count: int,
) -> list[TaxonomyNodeCreate]:
    remaining = max_l1_l2_count
    limited_nodes: list[TaxonomyNodeCreate] = []
    for node in nodes:
        if remaining <= 1:
            break
        node_copy = node.model_copy(deep=True)
        child_budget = max(1, remaining - 1)
        node_copy.children = node_copy.children[:child_budget]
        if not node_copy.children:
            continue
        limited_nodes.append(node_copy)
        remaining -= 1 + len(node_copy.children)
    return limited_nodes


def _limit_taxonomy_tree_to_generation_config(
    nodes: list[TaxonomyNodeCreate],
    generation_config: TaxonomyGenerationRuntimeConfig,
) -> list[TaxonomyNodeCreate]:
    limited_nodes = _limit_l1_l2_nodes(
        nodes,
        generation_config.first_level_max_count,
    )
    for l1_node in limited_nodes:
        for l2_node in l1_node.children:
            l2_node.children = l2_node.children[
                : generation_config.third_level_max_count
            ]
    return limited_nodes


def _leaf_count_exceeds_generation_config(
    nodes: list[TaxonomyNodeCreate],
    generation_config: TaxonomyGenerationRuntimeConfig,
) -> bool:
    if _count_l1_l2_nodes(nodes) > generation_config.first_level_max_count:
        return True
    for l1_node in nodes:
        for l2_node in l1_node.children:
            if len(l2_node.children) > generation_config.third_level_max_count:
                return True
    return False


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
    active_confidence_threshold: float,
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
- active_confidence_threshold={active_confidence_threshold}。
- tags 只能输出 confidence >= active_confidence_threshold 的已有 leaf。
- 如果最接近的已有 leaf 置信度低于 active_confidence_threshold，不要把它输出到 tags；当 enable_optimization=true 时，改在 candidates 中提出一个更贴切的三级 leaf 候选，交给后续健康自检判断是否新增或复用已有 leaf。
- 若无法覆盖，写 unmatched_reason。
- enable_optimization={str(enable_optimization).lower()}。只有为 true 时，才允许输出 candidates。
- candidates 必须是完整三级路径，字段 path 为长度 3 的数组。
- candidates 只是候选新增标签建议，不做最终新增决定；冗余和是否新增由后续 Taxonomy 健康自检 Agent 统一判断。
- 优先复用候选 leaf；只有当前 leaf 无法覆盖且 enable_optimization=true 时才输出 candidates。

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


def recommend_existing_taxonomy_tags_forced(
    *,
    document_title: str,
    document_content: str,
    leaf_nodes: list[TaxonomyNode],
    llm: LLM | None = None,
) -> TaxonomyExistingLabelFallbackResult:
    if not leaf_nodes:
        raise ValueError("Cannot fallback-tag documents without active leaf nodes")

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
你是企业知识库兜底打标 Agent。前序打标没有产生可用标签，但当前文档必须绑定已有三级 leaf。

必须遵守：
- 只输出 JSON 对象。
- 只能从候选 leaf id 中选择标签，不允许输出新增标签或候选标签。
- 必须至少选择 1 个最合适的已有 leaf，最多 3 个。
- 如果没有完美匹配，也要选择语义最接近、最能承载该文档主要内容的已有 leaf。
- confidence 为 0 到 1；不确定时可以降低 confidence，但不要空返回。

输出 JSON 结构：
{{
  "tags": [{{"leaf_node_id": "...", "confidence": 0.74, "evidence": "..."}}],
  "reason": "说明为什么这些已有 leaf 是当前最适合复用的标签"
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
        flow=LLMFlow.TAXONOMY_EXISTING_LABEL_FALLBACK,
        max_tokens=1800,
    )
    valid_leaf_ids = {node.id for node in leaf_nodes}
    tags: list[TaxonomyTagRecommendation] = []
    for raw_tag in parsed.get("tags", []):
        if not isinstance(raw_tag, dict):
            continue
        leaf_id = raw_tag.get("leaf_node_id")
        if not isinstance(leaf_id, str) or leaf_id not in valid_leaf_ids:
            continue
        tags.append(
            TaxonomyTagRecommendation(
                leaf_node_id=leaf_id,
                confidence=_coerce_confidence(raw_tag.get("confidence")),
                evidence=str(raw_tag.get("evidence") or ""),
            )
        )

    reason = parsed.get("reason")
    return TaxonomyExistingLabelFallbackResult(
        tags=tags,
        reason=reason if isinstance(reason, str) else "",
    )


def _coerce_str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def review_taxonomy_candidate_labels(
    *,
    candidates: list[TaxonomyCandidateForHealthCheck],
    leaf_nodes: list[TaxonomyNode],
    l2_nodes: list[TaxonomyNode],
    optimization_strength: str | None,
    llm: LLM | None = None,
) -> list[TaxonomyCandidateHealthDecision]:
    if not candidates:
        return []
    if not leaf_nodes:
        raise ValueError("Cannot health-check taxonomy candidates without leaf nodes")
    if not l2_nodes:
        raise ValueError("Cannot add taxonomy leaf labels without l2 nodes")

    llm = llm or get_default_llm(temperature=0)
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    valid_candidate_ids = set(candidate_by_id)
    valid_leaf_ids = {node.id for node in leaf_nodes}
    valid_l2_ids = {node.id for node in l2_nodes}
    candidate_cards = json.dumps(
        [
            {
                "candidate_id": candidate.candidate_id,
                "document_id": candidate.document_id,
                "path": candidate.path,
                "definition": candidate.definition,
                "evidence": candidate.evidence,
                "confidence": candidate.confidence,
            }
            for candidate in candidates
        ],
        ensure_ascii=False,
        indent=2,
    )
    leaf_cards = "\n".join(
        f"- id: {node.id}\n  path: {node.full_path}\n  definition: {node.definition}\n"
        f"  applicability: {node.applicability}\n"
        f"  keywords: {', '.join(node.keywords or [])}\n"
        f"  synonyms: {', '.join(node.synonyms or [])}\n"
        f"  positive: {', '.join(node.positive_examples or [])}\n"
        f"  negative: {', '.join(node.negative_examples or [])}"
        for node in leaf_nodes
    )
    l2_cards = "\n".join(
        f"- id: {node.id}\n  path: {node.full_path}\n  definition: {node.definition}\n"
        f"  applicability: {node.applicability}\n"
        f"  keywords: {', '.join(node.keywords or [])}\n"
        f"  synonyms: {', '.join(node.synonyms or [])}"
        for node in l2_nodes
    )
    prompt = f"""
你是 Taxonomy 健康自检 Agent。请统一审核一批候选新增 leaf 标签。

业务目标：
- 新增标签是例外，不是默认行为。
- 优先复用已有 leaf；只有已有 leaf 不能覆盖时才允许新增。
- 新增时优先在已有一级/二级主干下补充最小粒度 leaf，避免新增主干枝。
- 维护标签体系简洁、低冗余、低复杂度。

必须遵守：
- 只输出 JSON 对象。
- decisions 必须覆盖每个 candidate_id，且每个 candidate_id 只能出现一次。
- action 只能是 reuse_existing、add_leaf、reject、needs_handling。
- reuse_existing 必须给出已有 leaf 的 suggested_reuse_node_id。
- reject 只表示“拒绝新增该候选 leaf，因为它与已有 leaf 冗余”；必须给出已有 leaf 的 suggested_reuse_node_id，后续文档会绑定该已有 leaf。
- add_leaf 必须给出已有二级节点 parent_l2_node_id，不允许新增一级或二级节点。
- add_leaf 的 leaf 需要包含 name、definition、applicability、keywords、synonyms、positive_examples、negative_examples。
- 如果候选需要新增一级或二级主干，输出 needs_handling，不要 add_leaf。
- 如果候选只是同义词、命名变体、细粒度重复或可被已有 leaf 覆盖，输出 reuse_existing。
- 如果候选语义不清、证据不足、路径不符合三级结构，且无法匹配到已有 leaf，输出 needs_handling，不要输出 reject。
- 批量内候选之间也要去重；语义相同的多个候选应复用同一个 add_leaf 决策或复用已有 leaf。
- optimization_strength={optimization_strength or ""}

输出 JSON 结构：
{{
  "decisions": [
    {{
      "candidate_id": 1,
      "action": "reuse_existing|add_leaf|reject|needs_handling",
      "reason": "...",
      "suggested_reuse_node_id": null,
      "parent_l2_node_id": null,
      "leaf": {{
        "name": "...",
        "definition": "...",
        "applicability": "...",
        "keywords": ["..."],
        "synonyms": ["..."],
        "positive_examples": ["..."],
        "negative_examples": ["..."]
      }}
    }}
  ]
}}

已有二级节点，只能从这里选择新增 leaf 的挂载位置：
{l2_cards}

已有 leaf，用于复用和冗余判断：
{leaf_cards}

候选新增标签：
{candidate_cards}
"""
    parsed = _invoke_json(
        llm=llm,
        prompt=prompt,
        flow=LLMFlow.TAXONOMY_HEALTH_CHECK,
        max_tokens=max(2500, len(candidates) * 500),
    )
    raw_decisions = parsed.get("decisions")
    if not isinstance(raw_decisions, list):
        raise ValueError("LLM taxonomy health response did not include decisions")

    decisions: list[TaxonomyCandidateHealthDecision] = []
    seen_candidate_ids: set[int] = set()
    for raw_decision in raw_decisions:
        if not isinstance(raw_decision, dict):
            continue
        try:
            candidate_id = int(raw_decision.get("candidate_id"))
        except (TypeError, ValueError):
            continue
        if candidate_id not in valid_candidate_ids or candidate_id in seen_candidate_ids:
            continue

        action = str(raw_decision.get("action") or "needs_handling").strip()
        if action not in TAXONOMY_HEALTH_DECISION_ACTIONS:
            action = "needs_handling"

        suggested_reuse_node_id = raw_decision.get("suggested_reuse_node_id")
        if suggested_reuse_node_id is not None:
            suggested_reuse_node_id = str(suggested_reuse_node_id).strip() or None
        parent_l2_node_id = raw_decision.get("parent_l2_node_id")
        if parent_l2_node_id is not None:
            parent_l2_node_id = str(parent_l2_node_id).strip() or None

        if (
            action in {"reuse_existing", "reject"}
            and suggested_reuse_node_id not in valid_leaf_ids
        ):
            action = "needs_handling"
            suggested_reuse_node_id = None
        if action == "add_leaf" and parent_l2_node_id not in valid_l2_ids:
            action = "needs_handling"
            parent_l2_node_id = None

        raw_leaf = raw_decision.get("leaf")
        leaf = raw_leaf if isinstance(raw_leaf, dict) else {}
        candidate = candidate_by_id[candidate_id]
        fallback_name = candidate.path[-1] if candidate.path else "未命名标签"
        leaf_name = str(leaf.get("name") or fallback_name).strip()
        if action == "add_leaf" and not leaf_name:
            action = "needs_handling"

        decisions.append(
            TaxonomyCandidateHealthDecision(
                candidate_id=candidate_id,
                action=action,
                reason=str(raw_decision.get("reason") or "").strip(),
                suggested_reuse_node_id=suggested_reuse_node_id,
                parent_l2_node_id=parent_l2_node_id,
                leaf_name=leaf_name or None,
                definition=str(leaf.get("definition") or candidate.definition).strip(),
                applicability=str(
                    leaf.get("applicability") or candidate.definition
                ).strip(),
                keywords=_coerce_str_list(leaf.get("keywords")) or [leaf_name],
                synonyms=_coerce_str_list(leaf.get("synonyms")),
                positive_examples=_coerce_str_list(leaf.get("positive_examples"))
                or [candidate.evidence],
                negative_examples=_coerce_str_list(leaf.get("negative_examples"))
                or ["不涉及该标签定义的文档"],
            )
        )
        seen_candidate_ids.add(candidate_id)

    for candidate in candidates:
        if candidate.candidate_id not in seen_candidate_ids:
            decisions.append(
                TaxonomyCandidateHealthDecision(
                    candidate_id=candidate.candidate_id,
                    action="needs_handling",
                    reason="健康自检未返回该候选标签的判断",
                )
            )

    return decisions


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
