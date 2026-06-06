export type TaxonomyNodeLevel = "l1" | "l2" | "leaf";
export type TaxonomyNodeStatus =
  | "draft"
  | "active"
  | "modified"
  | "disabled"
  | "deleted";
export type TaxonomyNodeSource =
  | "system_default"
  | "industry_template"
  | "ai_generated"
  | "manual"
  | "task_generated";
export type TaxonomyVersionStatus =
  | "draft"
  | "active"
  | "superseded"
  | "deprecated";
export type TaxonomyVersionSource =
  | "default_template"
  | "ai_generated"
  | "manual"
  | "tagging_optimization";
export type TaxonomySummaryStatus = "pending" | "complete" | "failed";
export type TaxonomyTaggingSource = "summary" | "original";
export type TaxonomyTaggingTaskStatus =
  | "pending"
  | "running"
  | "complete"
  | "failed"
  | "completed_with_errors";
export type TaxonomySearchApplyTo = "chat" | "search" | "both";
export type TaxonomySearchRecommendedAction =
  | "none"
  | "suggest"
  | "soft_filter"
  | "hard_filter";
export type TaxonomyTagSource =
  | "ai_recommended"
  | "task_generated"
  | "admin_confirmed"
  | "retagged"
  | "manual";
export type TaxonomyReviewStatus =
  | "unconfirmed"
  | "confirmed"
  | "rejected"
  | "modified";
export type TaxonomyAssignmentStatus =
  | "active"
  | "stale"
  | "needs_review"
  | "needs_retag"
  | "depends_on_disabled_label"
  | "tagging_failed";
export type TaxonomyArticleLabelStatus = Exclude<
  TaxonomyAssignmentStatus,
  "stale"
>;

export interface TaxonomyNode {
  id?: string | null;
  parent_id?: string | null;
  level: TaxonomyNodeLevel;
  code?: string | null;
  name: string;
  display_name?: string | null;
  definition: string;
  applicability: string;
  exclusion?: string | null;
  positive_examples: string[];
  negative_examples: string[];
  keywords: string[];
  synonyms: string[];
  tagging_guidance?: string | null;
  conflict_rules?: string | null;
  source: TaxonomyNodeSource;
  source_detail?: string | null;
  status: TaxonomyNodeStatus;
  sort_order: number;
  children: TaxonomyNode[];
  version_id?: number;
  full_path?: string;
  path_node_ids?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface TaxonomyVersion {
  id: number;
  taxonomy_id: number;
  version_number: number;
  status: TaxonomyVersionStatus;
  source: TaxonomyVersionSource;
  change_summary: string;
  change_reason?: string | null;
  effective_at?: string | null;
  health_summary?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  nodes: TaxonomyNode[];
}

export type TaxonomyDraftStreamEventType =
  | "stage"
  | "nodes"
  | "final"
  | "error";

export interface TaxonomyDraftStreamEvent {
  type: TaxonomyDraftStreamEventType;
  message?: string | null;
  nodes?: TaxonomyNode[] | null;
  node?: TaxonomyNode | null;
  parent_id?: string | null;
  progress?: number | null;
}

export interface TaxonomyGenerationConfig {
  first_level_candidate_multiplier: number;
  first_level_max_count: number;
  third_level_candidate_multiplier: number;
  third_level_max_count: number;
  third_level_parallelism: number;
  l1_l2_prompt_template: string;
  leaf_prompt_template: string;
}

export interface TaxonomyGenerationRuntimeConfig {
  first_level_candidate_multiplier: number;
  first_level_max_count: number;
  third_level_candidate_multiplier: number;
  third_level_max_count: number;
  third_level_parallelism: number;
  l1_l2_system_prompt: string;
  leaf_system_prompt: string;
}

export interface Taxonomy {
  id: number;
  name: string;
  active_version_id?: number | null;
  industry_context?: string | null;
  company_description?: string | null;
  created_at: string;
  updated_at: string;
  active_version?: TaxonomyVersion | null;
}

export interface TaxonomyCoverageStats {
  total_documents: number;
  labeled_documents: number;
  coverage_percent: number;
}

export interface DocumentTaxonomySummary {
  document_id: string;
  semantic_id?: string | null;
  summary?: string | null;
  status: TaxonomySummaryStatus;
  is_manual: boolean;
  failure_reason?: string | null;
  generated_at?: string | null;
  updated_at: string;
  current_label_status?: TaxonomyArticleLabelStatus | null;
}

export interface ArticleImportItem {
  file_name: string;
  document_id?: string | null;
  status: string;
  detail?: string | null;
}

export interface ArticleImportResponse {
  imported: ArticleImportItem[];
  failed: ArticleImportItem[];
}

export interface TaxonomyTaggingTask {
  id: number;
  version_id?: number | null;
  status: TaxonomyTaggingTaskStatus;
  source: TaxonomyTaggingSource;
  enable_optimization: boolean;
  optimization_strength?: string | null;
  total_docs: number;
  processed_docs: number;
  failed_docs: number;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at: string;
}

export interface DocumentTaxonomyTag {
  id: number;
  document_id: string;
  leaf_node_id?: string | null;
  full_path_snapshot: string;
  confidence: number;
  source: TaxonomyTagSource;
  is_primary: boolean;
  evidence?: string | null;
  unmatched_reason?: string | null;
  review_status: TaxonomyReviewStatus;
  status: TaxonomyAssignmentStatus;
  created_at: string;
  updated_at: string;
}

export interface TaxonomyDashboard {
  taxonomy?: Taxonomy | null;
  coverage: TaxonomyCoverageStats;
  summaries: DocumentTaxonomySummary[];
  recent_tasks: TaxonomyTaggingTask[];
}

export interface TaxonomyCandidateMatch {
  node_id: string;
  node_name: string;
  node_level: TaxonomyNodeLevel;
  path: string[];
  confidence: number;
  basis: string;
}

export interface TaxonomySearchDecision {
  matched: boolean;
  node_id?: string | null;
  node_level?: TaxonomyNodeLevel | null;
  path: string[];
  confidence: number;
  candidates: TaxonomyCandidateMatch[];
  expanded_leaf_ids: string[];
  recommended_action: TaxonomySearchRecommendedAction;
  reason: string;
  timed_out: boolean;
  elapsed_ms: number;
}
