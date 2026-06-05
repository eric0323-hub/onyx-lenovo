from __future__ import annotations

from collections.abc import Iterator
from threading import Lock

from onyx.db.enums import TaxonomyNodeLevel
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
    llm = StubLLM([malformed_json, repaired_json])

    nodes = generate_taxonomy_draft(
        company_description="客户问题、产品故障和解决方案",
        organization_context=None,
        knowledge_scope=None,
        classification_preferences=None,
        max_leaf_nodes=18,
        llm=llm,
    )

    assert len(llm.invoke_calls) == 2
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
      "children": []
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

    assert len(llm.invoke_calls) == 1
    assert llm.invoke_calls[0]["structured_response_format"] is None
    assert nodes[0].name == "客户服务"


def test_generate_taxonomy_draft_events_streams_layered_nodes_and_final() -> None:
    l1_json = """
{
  "nodes": [
    {
      "name": "客户服务",
      "definition": "客户咨询和售后支持相关内容",
      "applicability": "咨询、投诉、维修和解决方案",
      "keywords": ["客户"],
      "synonyms": ["客服"],
      "target_l2_count": 1,
      "target_leaf_count": 2
    },
    {
      "name": "产品知识",
      "definition": "产品说明、功能和使用指南",
      "applicability": "产品手册、功能说明和培训资料",
      "keywords": ["产品"],
      "synonyms": ["产品资料"],
      "target_l2_count": 1,
      "target_leaf_count": 2
    }
  ]
}
"""
    customer_l2_json = """
{
  "nodes": [
    {
      "name": "售后处理",
      "definition": "售后问题处理流程",
      "applicability": "报修、排查、维修进度",
      "keywords": ["售后"],
      "synonyms": ["维修"],
      "target_leaf_count": 2
    }
  ]
}
"""
    product_l2_json = """
{
  "nodes": [
    {
      "name": "产品说明",
      "definition": "产品功能和使用说明",
      "applicability": "说明书、功能介绍、培训材料",
      "keywords": ["说明"],
      "synonyms": ["手册"],
      "target_leaf_count": 2
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
            ("请先生成一级标签大纲", l1_json),
            ("当前二级标签：\n- id: generated.l1.0.l2.0", customer_leaf_json),
            ("当前二级标签：\n- id: generated.l1.1.l2.0", product_leaf_json),
            ("当前一级标签：\n- id: generated.l1.0", customer_l2_json),
            ("当前一级标签：\n- id: generated.l1.1", product_l2_json),
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
            llm=llm,
        )
    )

    assert len(llm.invoke_calls) == 6
    assert events[0].type == "stage"
    assert any(event.message == "已生成「客户服务」下的二级标签" for event in events)
    assert any(event.message == "已生成「售后处理」下的三级标签" for event in events)
    assert events[-1].type == "final"
    assert events[-1].progress == 100
    assert events[-1].nodes is not None
    assert events[-1].nodes[0].children[0].children[0].name == "故障排查"
