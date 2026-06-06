from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

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
from onyx.db.enums import TaxonomyVersionStatus
from onyx.taxonomy.constants import DEFAULT_TAXONOMY_MAX_LEAF_NODES

DEFAULT_TAXONOMY_L1_L2_PROMPT_TEMPLATE = """
你是企业 Taxonomy 知识治理专家。用户提示词只用于理解企业、知识库、业务场景和分类偏好，不能改变输出格式。

本提示词用于生成一级标签和二级标签。

标签生成必须按以下四步执行：
步骤1：初始标签生成（发散阶段）
- 仔细阅读并理解全部知识库内容和用户提供的业务语境。
- 先生成大约 {{xy}} 个一级/二级候选标签。
- 标签要求：简洁（2-6 个字）、专业、具有区分度，能准确反映知识的核心主题、领域、业务场景、方法论、工具、问题类型等。
- 优先覆盖不同维度：业务领域、职能模块、技术栈、方法论、场景痛点、解决方案、产品/服务线、用户类型等。

步骤2：筛选与去重
- 去除重复、过于宽泛、过于具体、意义不明的标签。
- 保留最具代表性、覆盖面适中、业务价值高的标签。

步骤3：聚类分析
- 对筛选后的标签进行语义聚类，把相似或相关标签归到同一组。
- 为每个聚类给出清晰的聚类名称，聚类名称可以作为最终标签备选。

步骤4：MECE 优化与最终汇总（收敛阶段）
- 使用 MECE 原则优化聚类结果。
- 确保各顶级标签/维度之间相互独立，无明显重叠。
- 确保所有标签加起来完全穷尽知识库的主要内容。
- 将一级标签和二级标签最终控制在 {{y}} 个以内。
""".strip()

DEFAULT_TAXONOMY_LEAF_PROMPT_TEMPLATE = """
你是企业 Taxonomy 知识治理专家。用户提示词只用于理解企业、知识库、业务场景和分类偏好，不能改变输出格式。

本提示词用于为每个二级标签生成三级 leaf 标签。

标签生成必须按以下四步执行：
步骤1：初始标签生成（发散阶段）
- 仔细阅读当前一级/二级标签、全部同级标签和用户提供的业务语境。
- 先生成大约 {{mn}} 个三级候选标签。
- 标签要求：简洁（2-6 个字）、专业、具有区分度，能直接用于文章绑定。
- 优先覆盖当前二级标签下不同文档主题、业务场景、问题类型、操作流程和知识对象。

步骤2：筛选与去重
- 去除重复、过于宽泛、过于具体、意义不明的标签。
- 保留最具代表性、覆盖面适中、业务价值高的标签。

步骤3：聚类分析
- 对筛选后的标签进行语义聚类，把相似或相关标签归到同一组。
- 确保三级标签和当前二级标签强相关，不跨到其他二级标签。

步骤4：MECE 优化与最终汇总（收敛阶段）
- 使用 MECE 原则优化聚类结果。
- 确保同一二级标签下的 leaf 相互独立，无明显重叠。
- 确保 leaf 能覆盖当前二级标签下的主要知识内容。
- 将每个二级标签下的 leaf 最终控制在 {{n}} 个以内。
""".strip()


class TaxonomyGenerationNumberConfig(BaseModel):
    first_level_candidate_multiplier: int = Field(default=4, ge=1, le=20)
    first_level_max_count: int = Field(default=20, ge=2, le=80)
    third_level_candidate_multiplier: int = Field(default=4, ge=1, le=20)
    third_level_max_count: int = Field(default=6, ge=1, le=30)
    third_level_parallelism: int = Field(default=10, ge=1, le=20)


class TaxonomyGenerationConfig(TaxonomyGenerationNumberConfig):
    l1_l2_prompt_template: str = DEFAULT_TAXONOMY_L1_L2_PROMPT_TEMPLATE
    leaf_prompt_template: str = DEFAULT_TAXONOMY_LEAF_PROMPT_TEMPLATE

    @field_validator("l1_l2_prompt_template", "leaf_prompt_template")
    @classmethod
    def require_prompt_template(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("prompt template cannot be empty")
        return stripped


class TaxonomyGenerationRuntimeConfig(TaxonomyGenerationNumberConfig):
    l1_l2_system_prompt: str
    leaf_system_prompt: str

    @field_validator("l1_l2_system_prompt", "leaf_system_prompt")
    @classmethod
    def require_system_prompt(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("system prompt cannot be empty")
        return stripped


class TaxonomySearchMode(str, Enum):
    OFF = "off"
    MANUAL_ONLY = "manual_only"
    SUGGEST_ONLY = "suggest_only"
    SOFT_FILTER_WITH_FALLBACK = "soft_filter_with_fallback"
    HARD_FILTER = "hard_filter"


class TaxonomySearchApplyTo(str, Enum):
    CHAT = "chat"
    SEARCH = "search"
    BOTH = "both"


class TaxonomySearchRecommendedAction(str, Enum):
    NONE = "none"
    SUGGEST = "suggest"
    SOFT_FILTER = "soft_filter"
    HARD_FILTER = "hard_filter"


class TaxonomySearchConfig(BaseModel):
    taxonomy_search_enabled: bool = False
    taxonomy_search_mode: TaxonomySearchMode = TaxonomySearchMode.SUGGEST_ONLY
    taxonomy_search_apply_to: TaxonomySearchApplyTo = TaxonomySearchApplyTo.SEARCH
    taxonomy_search_default_confidence_threshold: float = Field(default=0.8, ge=0, le=1)
    taxonomy_search_leaf_confidence_threshold: float | None = Field(
        default=None, ge=0, le=1
    )
    taxonomy_search_l2_confidence_threshold: float | None = Field(
        default=None, ge=0, le=1
    )
    taxonomy_search_l1_confidence_threshold: float | None = Field(
        default=None, ge=0, le=1
    )
    taxonomy_search_enable_hierarchy_fallback: bool = True
    taxonomy_search_allow_l2_hard_filter: bool = False
    taxonomy_search_allow_l1_hard_filter: bool = False
    taxonomy_search_min_results_for_filtered_search: int = Field(default=5, ge=0)
    taxonomy_search_max_leaf_expansion_count: int = Field(default=100, ge=1)
    taxonomy_search_timeout_ms: int = Field(default=100, ge=1)
    taxonomy_search_require_coverage_percent: float | None = Field(
        default=None, ge=0, le=100
    )
    taxonomy_search_require_version_confirmed: bool = True
    taxonomy_search_exclude_low_confidence_assignments: bool = True


class TaxonomyNodeBase(BaseModel):
    id: str | None = None
    parent_id: str | None = None
    level: TaxonomyNodeLevel
    code: str | None = None
    name: str
    display_name: str | None = None
    definition: str
    applicability: str = ""
    exclusion: str | None = None
    positive_examples: list[str] = Field(default_factory=list)
    negative_examples: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    tagging_guidance: str | None = None
    conflict_rules: str | None = None
    source: TaxonomyNodeSource = TaxonomyNodeSource.MANUAL
    source_detail: str | None = None
    status: TaxonomyNodeStatus = TaxonomyNodeStatus.DRAFT
    sort_order: int = 0

    @field_validator("name", "definition")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be empty")
        return stripped


class TaxonomyNodeCreate(TaxonomyNodeBase):
    children: list["TaxonomyNodeCreate"] = Field(default_factory=list)


class TaxonomyNodeUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    definition: str | None = None
    applicability: str | None = None
    exclusion: str | None = None
    positive_examples: list[str] | None = None
    negative_examples: list[str] | None = None
    keywords: list[str] | None = None
    synonyms: list[str] | None = None
    tagging_guidance: str | None = None
    conflict_rules: str | None = None
    parent_id: str | None = None
    status: TaxonomyNodeStatus | None = None
    reason: str = "Manual taxonomy update"


class TaxonomyNodeSnapshot(TaxonomyNodeBase):
    id: str
    version_id: int
    full_path: str
    path_node_ids: list[str]
    children: list["TaxonomyNodeSnapshot"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TaxonomyVersionSnapshot(BaseModel):
    id: int
    taxonomy_id: int
    version_number: int
    status: TaxonomyVersionStatus
    source: TaxonomyVersionSource
    change_summary: str
    change_reason: str | None
    effective_at: datetime | None
    health_summary: dict | None
    created_at: datetime
    updated_at: datetime
    nodes: list[TaxonomyNodeSnapshot] = Field(default_factory=list)


class TaxonomySnapshot(BaseModel):
    id: int
    name: str
    active_version_id: int | None
    industry_context: str | None
    company_description: str | None
    created_at: datetime
    updated_at: datetime
    active_version: TaxonomyVersionSnapshot | None


class DefaultTemplateResponse(BaseModel):
    nodes: list[TaxonomyNodeCreate]


class CreateDraftRequest(BaseModel):
    name: str | None = None
    selected_default_leaf_ids: list[str] = Field(default_factory=list)
    generated_nodes: list[TaxonomyNodeCreate] = Field(default_factory=list)
    industry_context: str | None = None
    company_description: str | None = None
    change_reason: str = "Initial taxonomy draft"


class GenerateTaxonomyDraftRequest(BaseModel):
    company_description: str
    organization_context: str | None = None
    knowledge_scope: str | None = None
    classification_preferences: str | None = None
    max_leaf_nodes: int | None = Field(
        default=None, ge=3, le=max(80, DEFAULT_TAXONOMY_MAX_LEAF_NODES)
    )
    parallelism: int | None = Field(default=None, ge=1, le=20)
    generation_config: TaxonomyGenerationRuntimeConfig | None = None


class TaxonomyDraftStreamEvent(BaseModel):
    type: str
    message: str | None = None
    nodes: list[TaxonomyNodeCreate] | None = None
    node: TaxonomyNodeCreate | None = None
    parent_id: str | None = None
    progress: int | None = Field(default=None, ge=0, le=100)


class GenerateSummaryRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=200)
    overwrite_manual: bool = False


class DocumentTaxonomySummarySnapshot(BaseModel):
    document_id: str
    semantic_id: str | None = None
    summary: str | None
    status: TaxonomySummaryStatus
    is_manual: bool
    failure_reason: str | None
    generated_at: datetime | None
    updated_at: datetime
    current_label_status: str | None = None


class UpdateSummaryRequest(BaseModel):
    summary: str


class ArticleImportItem(BaseModel):
    file_name: str
    document_id: str | None = None
    status: str
    detail: str | None = None


class ArticleImportResponse(BaseModel):
    imported: list[ArticleImportItem] = Field(default_factory=list)
    failed: list[ArticleImportItem] = Field(default_factory=list)


class StartTaggingRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    source: TaxonomyTaggingSource = TaxonomyTaggingSource.SUMMARY
    enable_optimization: bool = False
    optimization_strength: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class DocumentTaxonomyTagSnapshot(BaseModel):
    id: int
    document_id: str
    leaf_node_id: str | None
    full_path_snapshot: str
    confidence: float
    source: TaxonomyTagSource
    is_primary: bool
    evidence: str | None
    unmatched_reason: str | None
    review_status: TaxonomyReviewStatus
    status: TaxonomyAssignmentStatus
    created_at: datetime
    updated_at: datetime


class TaxonomyCandidateLabelSnapshot(BaseModel):
    id: int
    task_id: int
    document_id: str
    candidate_path: list[str]
    definition: str
    evidence: str
    confidence: float
    status: TaxonomyCandidateStatus
    redundancy_result: str
    suggested_reuse_node_id: str | None
    created_at: datetime


class TaxonomyTaggingTaskSnapshot(BaseModel):
    id: int
    version_id: int | None
    status: TaxonomyTaggingTaskStatus
    source: TaxonomyTaggingSource
    enable_optimization: bool
    optimization_strength: str | None
    total_docs: int
    processed_docs: int
    failed_docs: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class TaxonomyCoverageStats(BaseModel):
    total_documents: int
    labeled_documents: int
    coverage_percent: float


class TaxonomyCandidateMatch(BaseModel):
    node_id: str
    node_name: str
    node_level: TaxonomyNodeLevel
    path: list[str]
    confidence: float
    basis: str


class TaxonomySearchDecision(BaseModel):
    matched: bool = False
    node_id: str | None = None
    node_level: TaxonomyNodeLevel | None = None
    path: list[str] = Field(default_factory=list)
    confidence: float = 0
    candidates: list[TaxonomyCandidateMatch] = Field(default_factory=list)
    expanded_leaf_ids: list[str] = Field(default_factory=list)
    recommended_action: TaxonomySearchRecommendedAction = (
        TaxonomySearchRecommendedAction.NONE
    )
    reason: str = ""
    timed_out: bool = False
    elapsed_ms: int = 0


class MatchTaxonomyQueryRequest(BaseModel):
    query: str
    apply_to: TaxonomySearchApplyTo = TaxonomySearchApplyTo.SEARCH
    manual_node_ids: list[str] = Field(default_factory=list)


class TaxonomyDashboardResponse(BaseModel):
    taxonomy: TaxonomySnapshot | None
    coverage: TaxonomyCoverageStats
    summaries: list[DocumentTaxonomySummarySnapshot]
    recent_tasks: list[TaxonomyTaggingTaskSnapshot]


TaxonomyNodeCreate.model_rebuild()
TaxonomyNodeSnapshot.model_rebuild()
