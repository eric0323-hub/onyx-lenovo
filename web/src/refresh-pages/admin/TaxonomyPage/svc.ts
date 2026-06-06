import { mutate } from "swr";
import { SWR_KEYS } from "@/lib/swr-keys";
import {
  ArticleImportResponse,
  DocumentTaxonomyTag,
  TaxonomyDraftStreamEvent,
  TaxonomyGenerationConfig,
  TaxonomyGenerationRuntimeConfig,
  TaxonomyNode,
  TaxonomySearchApplyTo,
  TaxonomySearchDecision,
  TaxonomyTaggingSource,
  TaxonomyTaggingTask,
  TaxonomyVersion,
} from "./types";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || payload?.message || response.statusText);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse<T>(response);
}

async function putJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse<T>(response);
}

export async function refreshTaxonomyData() {
  await Promise.all([
    mutate(SWR_KEYS.taxonomyDashboard),
    mutate(SWR_KEYS.taxonomyVersions),
  ]);
}

export async function fetchTaxonomyGenerationConfig(): Promise<TaxonomyGenerationConfig> {
  const response = await fetch("/api/admin/taxonomy/generation-config");
  return parseResponse<TaxonomyGenerationConfig>(response);
}

export async function updateTaxonomyGenerationConfig(
  config: TaxonomyGenerationConfig
): Promise<TaxonomyGenerationConfig> {
  return putJson<TaxonomyGenerationConfig>(
    "/api/admin/taxonomy/generation-config",
    config
  );
}

export async function generateTaxonomyDraft(args: {
  company_description: string;
  organization_context?: string | null;
  knowledge_scope?: string | null;
  classification_preferences?: string | null;
  max_leaf_nodes?: number;
  generation_config?: TaxonomyGenerationRuntimeConfig | null;
}): Promise<TaxonomyNode[]> {
  const response = await postJson<{ nodes: TaxonomyNode[] }>(
    "/api/admin/taxonomy/generate-draft",
    args
  );
  return response.nodes;
}

export async function generateTaxonomyDraftStream(
  args: {
    company_description: string;
    organization_context?: string | null;
    knowledge_scope?: string | null;
    classification_preferences?: string | null;
    max_leaf_nodes?: number;
    parallelism?: number;
    generation_config?: TaxonomyGenerationRuntimeConfig | null;
  },
  onEvent: (event: TaxonomyDraftStreamEvent) => void
): Promise<TaxonomyNode[]> {
  const response = await fetch("/api/admin/taxonomy/generate-draft/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(args),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || payload?.message || response.statusText);
  }
  if (!response.body) {
    throw new Error("标签体系生成流没有返回内容");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalNodes: TaxonomyNode[] | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const dataLines = rawEvent
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim());
      if (!dataLines.length) {
        continue;
      }

      const event = JSON.parse(
        dataLines.join("\n")
      ) as TaxonomyDraftStreamEvent;
      if (event.type === "error") {
        throw new Error(event.message || "标签体系生成失败");
      }
      if (event.type === "final" && event.nodes) {
        finalNodes = event.nodes;
      }
      onEvent(event);
    }
  }

  if (!finalNodes) {
    throw new Error("标签体系生成未返回最终结果");
  }
  return finalNodes;
}

export async function createTaxonomyDraft(args: {
  name?: string | null;
  selected_default_leaf_ids: string[];
  generated_nodes: TaxonomyNode[];
  company_description?: string | null;
  change_reason: string;
}): Promise<TaxonomyVersion> {
  const version = await postJson<TaxonomyVersion>(
    "/api/admin/taxonomy/draft",
    args
  );
  await refreshTaxonomyData();
  return version;
}

export async function activateTaxonomyVersion(
  versionId: number
): Promise<TaxonomyVersion> {
  const version = await postJson<TaxonomyVersion>(
    `/api/admin/taxonomy/version/${versionId}/activate`,
    {}
  );
  await refreshTaxonomyData();
  return version;
}

export async function generateSummaries(args: {
  document_ids: string[];
  limit: number;
  overwrite_manual: boolean;
}): Promise<{ processed: number }> {
  const result = await postJson<{ processed: number }>(
    "/api/admin/taxonomy/summaries/generate",
    args
  );
  await mutate(SWR_KEYS.taxonomyDashboard);
  return result;
}

export async function importArticles(files: File[]): Promise<ArticleImportResponse> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file);
  });

  const response = await fetch("/api/admin/taxonomy/articles/import", {
    method: "POST",
    body: formData,
  });
  const result = await parseResponse<ArticleImportResponse>(response);
  await mutate(SWR_KEYS.taxonomyDashboard);
  return result;
}

export async function updateSummary(
  documentId: string,
  summary: string
): Promise<void> {
  const response = await fetch(`/api/admin/taxonomy/summaries/${documentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ summary }),
  });
  await parseResponse<{ status: string }>(response);
  await Promise.all([
    mutate(SWR_KEYS.taxonomyDashboard),
    mutate(SWR_KEYS.taxonomyDocumentTags(documentId)),
  ]);
}

export async function runTagging(args: {
  document_ids: string[];
  source: TaxonomyTaggingSource;
  enable_optimization: boolean;
  optimization_strength?: string | null;
  limit: number;
}): Promise<TaxonomyTaggingTask> {
  const task = await postJson<TaxonomyTaggingTask>(
    "/api/admin/taxonomy/tagging/run",
    args
  );
  await mutate(SWR_KEYS.taxonomyDashboard);
  return task;
}

export async function fetchDocumentTaxonomyTags(
  documentId: string
): Promise<DocumentTaxonomyTag[]> {
  const response = await fetch(
    `/api/admin/taxonomy/documents/${encodeURIComponent(documentId)}/tags`
  );
  return parseResponse<DocumentTaxonomyTag[]>(response);
}

export async function matchTaxonomyQuery(args: {
  query: string;
  apply_to: TaxonomySearchApplyTo;
  manual_node_ids?: string[];
}): Promise<TaxonomySearchDecision> {
  return postJson<TaxonomySearchDecision>("/api/admin/taxonomy/match-query", {
    query: args.query,
    apply_to: args.apply_to,
    manual_node_ids: args.manual_node_ids ?? [],
  });
}
