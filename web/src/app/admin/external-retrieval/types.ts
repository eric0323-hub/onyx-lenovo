export type ExternalRetrievalAdapterType = "http_json" | "ontology";
export type ExternalRetrievalAuthType =
  | "none"
  | "bearer"
  | "api_key_header"
  | "basic";
export type ExternalRetrievalRequestMode =
  | "simple"
  | "standard"
  | "custom_template";
export type ExternalRetrievalCallStrategy =
  | "original_query_once"
  | "semantic_query_once"
  | "per_expanded_query";

export interface ExternalRetrievalAuthConfig {
  type: ExternalRetrievalAuthType;
  token?: string | null;
  api_key_header?: string | null;
  api_key?: string | null;
  username?: string | null;
  password?: string | null;
}

export interface ExternalRetrievalConfig {
  endpoint: string;
  method: "POST";
  headers: Record<string, string>;
  request_mode: ExternalRetrievalRequestMode;
  request_template?: Record<string, unknown> | null;
  result_path?: string | null;
  field_mapping: Record<string, string[]>;
  max_content_chars: number;
  score_scale?: number | null;
  allow_localhost: boolean;
  strict_result_validation: boolean;
}

export interface ExternalRetrievalDocumentSetView {
  id: number;
  name: string;
}

export interface ExternalRetrievalSourceSummary {
  id: number;
  name: string;
  description: string | null;
  adapter_type: ExternalRetrievalAdapterType;
  enabled: boolean;
  endpoint: string;
  timeout_ms: number;
  max_results: number;
  source_weight: number;
  min_confidence: number | null;
  call_strategy: ExternalRetrievalCallStrategy;
  document_sets: ExternalRetrievalDocumentSetView[];
  time_updated: string | null;
}

export interface ExternalRetrievalSourceView extends Omit<
  ExternalRetrievalSourceSummary,
  "endpoint" | "time_updated"
> {
  auth: ExternalRetrievalAuthConfig;
  config: ExternalRetrievalConfig;
  time_created: string | null;
  time_updated: string | null;
}

export interface ExternalRetrievalSourceUpsertRequest {
  name: string;
  description?: string | null;
  adapter_type: ExternalRetrievalAdapterType;
  enabled: boolean;
  auth: ExternalRetrievalAuthConfig;
  auth_changed: boolean;
  config: ExternalRetrievalConfig;
  timeout_ms: number;
  max_results: number;
  source_weight: number;
  min_confidence?: number | null;
  call_strategy: ExternalRetrievalCallStrategy;
  document_set_ids: number[];
}

export interface ExternalRetrievalInvalidResult {
  index: number;
  reason: string;
  available_fields: string[];
}

export interface NormalizedExternalRetrievalResult {
  index: number;
  title: string;
  content: string;
  url?: string | null;
  score: number;
  confidence?: number | null;
  source_id?: string | null;
  dedupe_key: string;
  document_id: string;
  metadata: Record<string, string | string[]>;
  warnings: string[];
}

export interface ExternalRetrievalTestResult {
  success: boolean;
  latency_ms?: number | null;
  normalized_results: NormalizedExternalRetrievalResult[];
  invalid_results: ExternalRetrievalInvalidResult[];
  warnings: string[];
  raw_response?: unknown;
  error_code?: string | null;
  message?: string | null;
}
