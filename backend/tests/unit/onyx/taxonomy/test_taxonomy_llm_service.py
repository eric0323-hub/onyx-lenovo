from __future__ import annotations

from collections.abc import Iterator
from threading import Lock

from onyx.db.enums import TaxonomyNodeLevel
from onyx.db.enums import TaxonomyNodeSource
from onyx.db.enums import TaxonomyNodeStatus
from onyx.db.models import TaxonomyNode
from onyx.llm.constants import LlmProviderNames
from onyx.llm.interfaces import LLM
from onyx.llm.interfaces import LLMConfig
from onyx.llm.interfaces import LLMUserIdentity
from onyx.llm.model_response import Choice
from onyx.llm.model_response import Message
from onyx.llm.model_response import ModelResponse
from onyx.llm.model_response import ModelResponseStream
from onyx.llm.models import LanguageModelInput
from onyx.llm.models import ReasoningEffort
from onyx.llm.models import ToolChoiceOptions
from onyx.taxonomy.llm_service import generate_taxonomy_draft
from onyx.taxonomy.llm_service import generate_taxonomy_draft_events
from onyx.taxonomy.llm_service import review_taxonomy_candidate_labels
from onyx.taxonomy.llm_service import TaxonomyCandidateForHealthCheck
from onyx.taxonomy.models import TaxonomyGenerationRuntimeConfig


class StubLLM(LLM):
    def __init__(
        self,
        responses: list[str],
        *,
        model_provider: str = LlmProviderNames.OPENAI,
    ) -> None:
        self._responses = responses
        self._model_provider = model_provider
        self.invoke_calls: list[dict[str, object]] = []
        self._lock = Lock()

    @property
    def config(self) -> LLMConfig:
        return LLMConfig(
            model_provider=self._model_provider,
            model_name="test-model",
            temperature=0,
            max_input_tokens=10000,
        )

    def invoke(
        self,
        prompt: LanguageModelInput,
        _tools: list[dict] | None = None,
        _tool_choice: ToolChoiceOptions | None = None,
        structured_response_format: dict | None = None,
        _timeout_override: int | None = None,
        max_tokens: int | None = None,
        reasoning_effort: ReasoningEffort = ReasoningEffort.AUTO,
        _user_identity: LLMUserIdentity | None = None,
    ) -> ModelResponse:
        self.invoke_calls.append(
            {
                "prompt": prompt,
                "structured_response_format": structured_response_format,
                "max_tokens": max_tokens,
                "reasoning_effort": reasoning_effort,
            }
        )
        with self._lock:
            content = self._responses.pop(0)
        return ModelResponse(
            id="response-id",
            created="0",
            choice=Choice(message=Message(content=content)),
        )

    def stream(
        self,
        prompt: LanguageModelInput,
        tools: list[dict] | None = None,
        tool_choice: ToolChoiceOptions | None = None,
        structured_response_format: dict | None = None,
        timeout_override: int | None = None,
        max_tokens: int | None = None,
        reasoning_effort: ReasoningEffort = ReasoningEffort.AUTO,
        user_identity: LLMUserIdentity | None = None,
    ) -> Iterator[ModelResponseStream]:
        raise NotImplementedError


class RoutingStubLLM(StubLLM):
    def __init__(self, routes: list[tuple[str, str]]) -> None:
        super().__init__([])
        self._routes = routes

    def invoke(
        self,
        prompt: LanguageModelInput,
        _tools: list[dict] | None = None,
        _tool_choice: ToolChoiceOptions | None = None,
        structured_response_format: dict | None = None,
        _timeout_override: int | None = None,
        max_tokens: int | None = None,
        reasoning_effort: ReasoningEffort = ReasoningEffort.AUTO,
        _user_identity: LLMUserIdentity | None = None,
    ) -> ModelResponse:
        self.invoke_calls.append(
            {
                "prompt": prompt,
                "structured_response_format": structured_response_format,
                "max_tokens": max_tokens,
                "reasoning_effort": reasoning_effort,
            }
        )
        prompt_text = getattr(prompt, "content", str(prompt))
        for marker, content in self._routes:
            if marker in prompt_text:
                return ModelResponse(
                    id="response-id",
                    created="0",
                    choice=Choice(message=Message(content=content)),
                )
        raise AssertionError(f"No stub response for prompt: {prompt_text[:200]}")


def _taxonomy_node(
    *,
    node_id: str,
    level: TaxonomyNodeLevel,
    name: str,
    parent_id: str | None = None,
    code: str | None = None,
) -> TaxonomyNode:
    return TaxonomyNode(
        id=node_id,
        version_id=1,
        parent_id=parent_id,
        level=level,
        code=code or node_id,
        name=name,
        full_path=f"客户服务 / 售后处理 / {name}"
        if level == TaxonomyNodeLevel.LEAF
        else f"客户服务 / {name}",
        path_node_ids=["l1", parent_id or node_id, node_id]
        if level == TaxonomyNodeLevel.LEAF
        else ["l1", node_id],
        sort_order=0,
        definition=f"{name}定义",
        applicability=f"{name}适用范围",
        positive_examples=[f"{name}正例"],
        negative_examples=[f"{name}反例"],
        keywords=[name],
        synonyms=[],
        source=TaxonomyNodeSource.MANUAL,
        status=TaxonomyNodeStatus.ACTIVE,
    )


def test_generate_taxonomy_draft_repairs_malformed_json() -> None:
    malformed_json = """
{
  "nodes": [
    {
      "name": "客户服务"
      "definition": "客户问题和服务处理相关内容",
      "applicability": "客户咨询、问题排查、售后支持",
      "keywords": ["客户"],
      "synonyms": ["客服"],
      "children": []
    }
  ]
}
"""
    repaired_json = """
{
  "nodes": [
    {
      "name": "客户服务",
      "definition": "客户问题和服务处理相关内容",
      "applicability": "客户咨询、问题排查、售后支持",
      "keywords": ["客户"],
      "synonyms": ["客服"],
      "children": [
        {
          "name": "问题处理",
          "definition": "客户问题识别、分流和处理流程",
          "applicability": "咨询、投诉、故障处理",
          "keywords": ["问题"],
          "synonyms": ["客诉"],
          "children": [
            {
              "name": "故障排查",
              "definition": "产品故障、异常现象和定位处理",
              "applicability": "故障定位、解决方案、排查步骤",
              "keywords": ["故障"],
              "synonyms": ["异常"],
              "positive_examples": ["设备无法启动"],
              "negative_examples": ["销售合同审批"]
            }
          ]
        }
      ]
    }
  ]
}
"""
    leaf_json = """
{
  "nodes": [
    {
      "name": "故障排查",
      "definition": "产品故障、异常现象和定位处理",
      "applicability": "故障定位、解决方案、排查步骤",
      "keywords": ["故障"],
      "synonyms": ["异常"],
      "positive_examples": ["设备无法启动"],
      "negative_examples": ["销售合同审批"]
    }
  ]
}
"""
    llm = StubLLM([malformed_json, repaired_json, leaf_json, repaired_json])

    nodes = generate_taxonomy_draft(
        company_description="客户问题、产品故障和解决方案",
        organization_context=None,
        knowledge_scope=None,
        classification_preferences=None,
        max_leaf_nodes=18,
        llm=llm,
    )

    assert len(llm.invoke_calls) == 4
    assert all(
        call["structured_response_format"] == {"type": "json_object"}
        for call in llm.invoke_calls
    )
    assert nodes[0].level == TaxonomyNodeLevel.L1
    assert nodes[0].name == "客户服务"
    assert nodes[0].children[0].level == TaxonomyNodeLevel.L2
    assert nodes[0].children[0].children[0].level == TaxonomyNodeLevel.LEAF
    assert nodes[0].children[0].children[0].name == "故障排查"


def test_generate_taxonomy_draft_does_not_force_json_mode_for_other_providers() -> None:
    llm = StubLLM(
        [
            """
{
  "nodes": [
    {
      "name": "客户服务",
      "definition": "客户问题和服务处理相关内容",
      "applicability": "客户咨询、问题排查、售后支持",
      "keywords": ["客户"],
      "synonyms": ["客服"],
            "children": [
              {
                "name": "问题处理",
                "definition": "客户问题识别、分流和处理流程",
                "applicability": "咨询、投诉、故障处理",
                "keywords": ["问题"],
                "synonyms": ["客诉"]
              }
            ]
    }
  ]
}
""",
            """
{
  "nodes": [
    {
      "name": "故障排查",
      "definition": "产品故障、异常现象和定位处理",
      "applicability": "故障定位、解决方案、排查步骤",
      "keywords": ["故障"],
      "synonyms": ["异常"],
      "positive_examples": ["设备无法启动"],
      "negative_examples": ["销售合同审批"]
    }
  ]
}
""",
            """
{
  "nodes": [
    {
      "name": "客户服务",
      "definition": "客户问题和服务处理相关内容",
      "applicability": "客户咨询、问题排查、售后支持",
      "keywords": ["客户"],
      "synonyms": ["客服"],
      "children": [
        {
          "name": "问题处理",
          "definition": "客户问题识别、分流和处理流程",
          "applicability": "咨询、投诉、故障处理",
          "keywords": ["问题"],
          "synonyms": ["客诉"],
          "children": [
            {
              "name": "故障排查",
              "definition": "产品故障、异常现象和定位处理",
              "applicability": "故障定位、解决方案、排查步骤",
              "keywords": ["故障"],
              "synonyms": ["异常"],
              "positive_examples": ["设备无法启动"],
              "negative_examples": ["销售合同审批"]
            }
          ]
        }
      ]
    }
  ]
}
"""
        ],
        model_provider=LlmProviderNames.ANTHROPIC,
    )

    nodes = generate_taxonomy_draft(
        company_description="客户问题、产品故障和解决方案",
        organization_context=None,
        knowledge_scope=None,
        classification_preferences=None,
        max_leaf_nodes=18,
        llm=llm,
    )

    assert len(llm.invoke_calls) == 3
    assert all(call["structured_response_format"] is None for call in llm.invoke_calls)
    assert nodes[0].name == "客户服务"


def test_generate_taxonomy_draft_events_streams_layered_nodes_and_final() -> None:
    l1_l2_json = """
{
  "nodes": [
    {
      "name": "客户服务",
      "definition": "客户咨询和售后支持相关内容",
      "applicability": "咨询、投诉、维修和解决方案",
      "keywords": ["客户"],
      "synonyms": ["客服"],
      "children": [
        {
          "name": "售后处理",
          "definition": "售后问题处理流程",
          "applicability": "报修、排查、维修进度",
          "keywords": ["售后"],
          "synonyms": ["维修"]
        }
      ]
    },
    {
      "name": "产品知识",
      "definition": "产品说明、功能和使用指南",
      "applicability": "产品手册、功能说明和培训资料",
      "keywords": ["产品"],
      "synonyms": ["产品资料"],
      "children": [
        {
          "name": "产品说明",
          "definition": "产品功能和使用说明",
          "applicability": "说明书、功能介绍、培训材料",
          "keywords": ["说明"],
          "synonyms": ["手册"]
        }
      ]
    }
  ]
}
"""
    customer_leaf_json = """
{
  "nodes": [
    {
      "name": "故障排查",
      "definition": "产品故障定位和排查步骤",
      "applicability": "故障现象、排查路径、解决方案",
      "keywords": ["故障"],
      "synonyms": ["异常"],
      "positive_examples": ["设备无法启动"],
      "negative_examples": ["产品功能介绍"]
    },
    {
      "name": "维修进度",
      "definition": "维修工单进度和处理状态",
      "applicability": "工单状态、维修排期、处理结果",
      "keywords": ["工单"],
      "synonyms": ["维修状态"],
      "positive_examples": ["维修预计完成时间"],
      "negative_examples": ["产品参数说明"]
    }
  ]
}
"""
    product_leaf_json = """
{
  "nodes": [
    {
      "name": "功能说明",
      "definition": "产品功能、模块和使用方式",
      "applicability": "功能说明、模块介绍、操作步骤",
      "keywords": ["功能"],
      "synonyms": ["模块"],
      "positive_examples": ["如何启用自动巡检"],
      "negative_examples": ["维修工单状态"]
    },
    {
      "name": "培训资料",
      "definition": "面向员工或客户的产品培训内容",
      "applicability": "培训课件、操作演示、学习资料",
      "keywords": ["培训"],
      "synonyms": ["课程"],
      "positive_examples": ["新员工产品培训"],
      "negative_examples": ["客户投诉处理"]
    }
  ]
}
"""
    optimized_json = """
{
  "nodes": [
    {
      "name": "客户服务",
      "definition": "客户咨询和售后支持相关内容",
      "applicability": "咨询、投诉、维修和解决方案",
      "keywords": ["客户"],
      "synonyms": ["客服"],
      "children": [
        {
          "name": "售后处理",
          "definition": "售后问题处理流程",
          "applicability": "报修、排查、维修进度",
          "keywords": ["售后"],
          "synonyms": ["维修"],
          "children": [
            {
              "name": "故障排查",
              "definition": "产品故障定位和排查步骤",
              "applicability": "故障现象、排查路径、解决方案",
              "keywords": ["故障"],
              "synonyms": ["异常"],
              "positive_examples": ["设备无法启动"],
              "negative_examples": ["产品功能介绍"]
            },
            {
              "name": "维修进度",
              "definition": "维修工单进度和处理状态",
              "applicability": "工单状态、维修排期、处理结果",
              "keywords": ["工单"],
              "synonyms": ["维修状态"],
              "positive_examples": ["维修预计完成时间"],
              "negative_examples": ["产品参数说明"]
            }
          ]
        }
      ]
    },
    {
      "name": "产品知识",
      "definition": "产品说明、功能和使用指南",
      "applicability": "产品手册、功能说明和培训资料",
      "keywords": ["产品"],
      "synonyms": ["产品资料"],
      "children": [
        {
          "name": "产品说明",
          "definition": "产品功能和使用说明",
          "applicability": "说明书、功能介绍、培训材料",
          "keywords": ["说明"],
          "synonyms": ["手册"],
          "children": [
            {
              "name": "功能说明",
              "definition": "产品功能、模块和使用方式",
              "applicability": "功能说明、模块介绍、操作步骤",
              "keywords": ["功能"],
              "synonyms": ["模块"],
              "positive_examples": ["如何启用自动巡检"],
              "negative_examples": ["维修工单状态"]
            },
            {
              "name": "培训资料",
              "definition": "面向员工或客户的产品培训内容",
              "applicability": "培训课件、操作演示、学习资料",
              "keywords": ["培训"],
              "synonyms": ["课程"],
              "positive_examples": ["新员工产品培训"],
              "negative_examples": ["客户投诉处理"]
            }
          ]
        }
      ]
    }
  ],
  "change_summary": {}
}
"""
    llm = RoutingStubLLM(
        [
            ("请一次性生成一级/二级标签树", l1_l2_json),
            ("当前二级标签：\n- id: generated.l1.0.l2.0", customer_leaf_json),
            ("当前二级标签：\n- id: generated.l1.1.l2.0", product_leaf_json),
            ("全局审稿 Agent", optimized_json),
        ]
    )

    events = list(
        generate_taxonomy_draft_events(
            company_description="客户问题、产品故障和解决方案",
            organization_context=None,
            knowledge_scope=None,
            classification_preferences=None,
            max_leaf_nodes=4,
            parallelism=10,
            generation_config=TaxonomyGenerationRuntimeConfig(
                first_level_candidate_multiplier=5,
                first_level_max_count=4,
                third_level_candidate_multiplier=3,
                third_level_max_count=2,
                third_level_parallelism=7,
                l1_l2_system_prompt="前端渲染后的一级二级提示词：X=5 Y=4 XY=20",
                leaf_system_prompt="前端渲染后的三级提示词：M=3 N=2 MN=6 P=7",
            ),
            llm=llm,
        )
    )

    assert len(llm.invoke_calls) == 4
    prompt_texts = [
        str(getattr(call["prompt"], "content", call["prompt"]))
        for call in llm.invoke_calls
    ]
    assert "前端渲染后的一级二级提示词：X=5 Y=4 XY=20" in prompt_texts[0]
    assert "前端渲染后的三级提示词" not in prompt_texts[0]
    assert all(
        "前端渲染后的三级提示词：M=3 N=2 MN=6 P=7" in prompt_text
        for prompt_text in prompt_texts[1:3]
    )
    assert all(
        "前端渲染后的一级二级提示词" not in prompt_text
        for prompt_text in prompt_texts[1:3]
    )
    assert "前端渲染后的一级二级提示词：X=5 Y=4 XY=20" in prompt_texts[3]
    assert "前端渲染后的三级提示词：M=3 N=2 MN=6 P=7" in prompt_texts[3]
    assert all("当前任务参数" not in prompt_text for prompt_text in prompt_texts)
    assert all("初始候选标签数量" not in prompt_text for prompt_text in prompt_texts)
    assert all("初始候选三级标签数量" not in prompt_text for prompt_text in prompt_texts)
    assert events[0].type == "stage"
    assert any(
        event.message == "一级/二级标签已完成 MECE 收敛，开始并行生成三级标签"
        for event in events
    )
    assert any(event.message == "已生成「售后处理」下的三级标签" for event in events)
    assert events[-1].type == "final"
    assert events[-1].progress == 100
    assert events[-1].nodes is not None
    assert events[-1].nodes[0].children[0].children[0].name == "故障排查"


def test_review_taxonomy_candidate_labels_sanitizes_agent_decisions() -> None:
    llm = StubLLM(
        [
            """
{
  "decisions": [
    {
      "candidate_id": 1,
      "action": "reuse_existing",
      "reason": "已有故障排查可覆盖",
      "suggested_reuse_node_id": "leaf_existing",
      "parent_l2_node_id": null,
      "leaf": null
    },
    {
      "candidate_id": 2,
      "action": "add_leaf",
      "reason": "需要补充最小粒度叶子",
      "suggested_reuse_node_id": null,
      "parent_l2_node_id": "l2_support",
      "leaf": {
        "name": "远程诊断",
        "definition": "远程排查和诊断设备问题",
        "applicability": "远程日志、远程检测、远程定位",
        "keywords": ["远程诊断"],
        "synonyms": ["远程排查"],
        "positive_examples": ["通过远程日志定位故障"],
        "negative_examples": ["线下维修排期"]
      }
    },
    {
      "candidate_id": 3,
      "action": "reuse_existing",
      "reason": "无效 leaf id",
      "suggested_reuse_node_id": "missing_leaf",
      "parent_l2_node_id": null,
      "leaf": null
    }
  ]
}
"""
        ]
    )

    decisions = review_taxonomy_candidate_labels(
        candidates=[
            TaxonomyCandidateForHealthCheck(
                candidate_id=1,
                document_id="doc-1",
                path=["客户服务", "售后处理", "故障排查变体"],
                definition="故障排查变体定义",
                evidence="设备无法启动",
                confidence=0.8,
            ),
            TaxonomyCandidateForHealthCheck(
                candidate_id=2,
                document_id="doc-2",
                path=["客户服务", "售后处理", "远程诊断"],
                definition="远程诊断定义",
                evidence="远程日志定位故障",
                confidence=0.9,
            ),
            TaxonomyCandidateForHealthCheck(
                candidate_id=3,
                document_id="doc-3",
                path=["客户服务", "售后处理", "未知复用"],
                definition="未知复用定义",
                evidence="未知证据",
                confidence=0.7,
            ),
            TaxonomyCandidateForHealthCheck(
                candidate_id=4,
                document_id="doc-4",
                path=["客户服务", "售后处理", "未返回候选"],
                definition="未返回定义",
                evidence="未返回证据",
                confidence=0.6,
            ),
        ],
        leaf_nodes=[
            _taxonomy_node(
                node_id="leaf_existing",
                level=TaxonomyNodeLevel.LEAF,
                name="故障排查",
                parent_id="l2_support",
            )
        ],
        l2_nodes=[
            _taxonomy_node(
                node_id="l2_support",
                level=TaxonomyNodeLevel.L2,
                name="售后处理",
            )
        ],
        optimization_strength="balanced",
        llm=llm,
    )

    decision_by_id = {decision.candidate_id: decision for decision in decisions}
    assert decision_by_id[1].action == "reuse_existing"
    assert decision_by_id[1].suggested_reuse_node_id == "leaf_existing"
    assert decision_by_id[2].action == "add_leaf"
    assert decision_by_id[2].parent_l2_node_id == "l2_support"
    assert decision_by_id[2].leaf_name == "远程诊断"
    assert decision_by_id[2].keywords == ["远程诊断"]
    assert decision_by_id[3].action == "needs_handling"
    assert decision_by_id[3].suggested_reuse_node_id is None
    assert decision_by_id[4].action == "needs_handling"
    assert len(llm.invoke_calls) == 1
