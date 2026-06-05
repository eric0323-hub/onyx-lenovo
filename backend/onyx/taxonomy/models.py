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
    max_leaf_nodes: int = Field(default=DEFAULT_TAXONOMY_MAX_LEAF_NODES, ge=3, le=80)
    parallelism: int = Field(default=10, ge=1, le=20)


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
