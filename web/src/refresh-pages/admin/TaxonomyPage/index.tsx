"use client";

import type { ChangeEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import CodeMirror from "@uiw/react-codemirror";
import { json, jsonParseLinter } from "@codemirror/lang-json";
import { linter, lintGutter } from "@codemirror/lint";
import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import Tree from "rc-tree";
import type { TreeNodeProps, TreeProps } from "rc-tree";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import { Hoverable } from "@opal/core";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { SWR_KEYS } from "@/lib/swr-keys";
import { ADMIN_ROUTES, type AdminRouteEntry } from "@/lib/admin-routes";
import * as SettingsLayouts from "@/layouts/settings-layouts";
import { Section } from "@/layouts/general-layouts";
import InputTypeIn from "@/refresh-components/inputs/InputTypeIn";
import InputTextArea from "@/refresh-components/inputs/InputTextArea";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import Switch from "@/refresh-components/inputs/Switch";
import Modal from "@/refresh-components/Modal";
import Tabs from "@/refresh-components/Tabs";
import {
  Button,
  Card,
  Divider,
  EmptyMessageCard,
  MessageCard,
  Tag,
  Text,
  Tooltip,
} from "@opal/components";
import {
  Card as CardLayout,
  Content,
  InputHorizontal,
  InputVertical,
} from "@opal/layouts";
import {
  SvgBlocks,
  SvgBookOpen,
  SvgBracketCurly,
  SvgBranch,
  SvgCheck,
  SvgChevronRight,
  SvgClock,
  SvgEdit,
  SvgExternalLink,
  SvgFileText,
  SvgLoader,
  SvgPlus,
  SvgProgressBars,
  SvgRefreshCw,
  SvgSearch,
  SvgSettings,
  SvgSparkle,
  SvgTag,
  SvgTrash,
  SvgUploadCloud,
  SvgX,
} from "@opal/icons";
import type { IconProps } from "@opal/types";
import { toast } from "@/hooks/useToast";
import {
  activateTaxonomyVersion,
  createTaxonomyDraft,
  deleteImportedArticle,
  fetchImportedArticleOriginal,
  fetchDocumentTaxonomyTags,
  fetchTaxonomyGenerationConfig,
  generateSummaries,
  generateTaxonomyDraftStream,
  getImportedArticleOriginalUrl,
  importArticles,
  matchTaxonomyQuery,
  runTagging,
  updateTaxonomyGenerationConfig,
  updateSummary,
} from "./svc";
import {
  DocumentTaxonomyTag,
  DocumentTaxonomySummary,
  TaxonomyDashboard,
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
import { useExpiringTaxonomyImportPoll } from "./useExpiringTaxonomyImportPoll";

interface TaxonomyTreeDataNode {
  key: string;
  title: string;
  path: number[];
  disableCheckbox: boolean;
  isLeaf: boolean;
  taxonomyNode: TaxonomyNode;
  leafIds: string[];
  children: TaxonomyTreeDataNode[];
}

interface TaxonomyTreeSelectionState {
  checkedKeys: string[];
  halfCheckedKeys: string[];
}

interface TaxonomyNodeActionTarget {
  path: number[];
  node: TaxonomyNode;
}

interface TaxonomyAddNodeTarget {
  parentPath: number[];
  parentNode?: TaxonomyNode;
  level: TaxonomyNode["level"];
}

interface TaxonomyGenerationStatus {
  message: string;
  progress: number;
}

interface PersistedTaxonomyGenerationState {
  prompt: string;
  status: TaxonomyGenerationStatus;
  nodes: TaxonomyNode[];
}

interface ArticleStage {
  title: string;
  description: string;
  progress: number;
  color: "amber" | "blue" | "green" | "gray";
}

type TaxonomyNodeListField =
  | "positive_examples"
  | "negative_examples"
  | "keywords"
  | "synonyms";

const TAXONOMY_GENERATION_STORAGE_KEY =
  "onyx.taxonomy.templateDraft.generation.v1";
const TAXONOMY_DASHBOARD_POLL_INTERVAL_MS = 3000;
const DEFAULT_TAXONOMY_GENERATION_CONFIG: TaxonomyGenerationConfig = {
  first_level_candidate_multiplier: 4,
  first_level_max_count: 20,
  third_level_candidate_multiplier: 4,
  third_level_max_count: 6,
  third_level_parallelism: 10,
  l1_l2_prompt_template: "",
  leaf_prompt_template: "",
};

function getTaxonomyGenerationCountMetrics(config: TaxonomyGenerationConfig) {
  return {
    firstStageInitialCount:
      config.first_level_candidate_multiplier * config.first_level_max_count,
    thirdStageInitialCount:
      config.third_level_candidate_multiplier * config.third_level_max_count,
  };
}

function getTaxonomyGenerationPromptVariables({
  config,
  companyDescription,
}: {
  config: TaxonomyGenerationConfig;
  companyDescription: string;
}) {
  const metrics = getTaxonomyGenerationCountMetrics(config);
  return {
    company_description: companyDescription,
    x: String(config.first_level_candidate_multiplier),
    y: String(config.first_level_max_count),
    xy: String(metrics.firstStageInitialCount),
    m: String(config.third_level_candidate_multiplier),
    n: String(config.third_level_max_count),
    mn: String(metrics.thirdStageInitialCount),
    p: String(config.third_level_parallelism),
  };
}

function renderTaxonomyGenerationPromptTemplate(
  template: string,
  variables: Record<string, string>
) {
  return template.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (match, key) => {
    return variables[key] ?? match;
  });
}

function buildTaxonomyGenerationRequestConfig({
  config,
  companyDescription,
}: {
  config: TaxonomyGenerationConfig;
  companyDescription: string;
}): TaxonomyGenerationRuntimeConfig {
  const variables = getTaxonomyGenerationPromptVariables({
    config,
    companyDescription,
  });

  return {
    first_level_candidate_multiplier: config.first_level_candidate_multiplier,
    first_level_max_count: config.first_level_max_count,
    third_level_candidate_multiplier: config.third_level_candidate_multiplier,
    third_level_max_count: config.third_level_max_count,
    third_level_parallelism: config.third_level_parallelism,
    l1_l2_system_prompt: renderTaxonomyGenerationPromptTemplate(
      config.l1_l2_prompt_template.trim(),
      variables
    ),
    leaf_system_prompt: renderTaxonomyGenerationPromptTemplate(
      config.leaf_prompt_template.trim(),
      variables
    ),
  };
}

function readPersistedTaxonomyGeneration(): PersistedTaxonomyGenerationState | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(TAXONOMY_GENERATION_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedTaxonomyGenerationState>;
    if (!parsed.prompt?.trim()) {
      return null;
    }
    return {
      prompt: parsed.prompt,
      status: {
        message: parsed.status?.message || "正在恢复标签体系生成",
        progress: parsed.status?.progress ?? 0,
      },
      nodes: Array.isArray(parsed.nodes) ? parsed.nodes : [],
    };
  } catch {
    return null;
  }
}

function writePersistedTaxonomyGeneration(
  state: PersistedTaxonomyGenerationState
) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    TAXONOMY_GENERATION_STORAGE_KEY,
    JSON.stringify(state)
  );
}

function clearPersistedTaxonomyGeneration() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(TAXONOMY_GENERATION_STORAGE_KEY);
}

function formatDate(value?: string | null) {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

function countNodes(nodes: TaxonomyNode[]) {
  const counts = { l1: 0, l2: 0, leaf: 0 };
  const visit = (node: TaxonomyNode) => {
    counts[node.level] += 1;
    node.children.forEach(visit);
  };
  nodes.forEach(visit);
  return counts;
}

function parseDocumentIds(value: string) {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseTaxonomyList(value: string) {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeOptionalText(value?: string | null) {
  const trimmed = value?.trim();
  return trimmed || null;
}

function normalizeTaxonomyList(values: string[]) {
  return values.map((item) => item.trim()).filter(Boolean);
}

function getSummaryStatusLabel(status: DocumentTaxonomySummary["status"]) {
  switch (status) {
    case "complete":
      return "摘要完成";
    case "failed":
      return "总结失败";
    case "pending":
      return "正在总结";
    default:
      return status;
  }
}

function getTaskStatusLabel(status: TaxonomyTaggingTask["status"]) {
  switch (status) {
    case "pending":
      return "等待打标签";
    case "running":
      return "正在打标签";
    case "complete":
      return "打标签完成";
    case "completed_with_errors":
      return "部分完成";
    case "failed":
      return "打标签失败";
    default:
      return status;
  }
}

function getTaskProgress(task?: TaxonomyTaggingTask) {
  if (!task || task.total_docs <= 0) {
    return 0;
  }
  return Math.min(
    100,
    Math.round((task.processed_docs / task.total_docs) * 100)
  );
}

function taxonomyTaskIsActive(task?: TaxonomyTaggingTask) {
  return task?.status === "running" || task?.status === "pending";
}

function taxonomyDashboardHasActiveProcessing(dashboard?: TaxonomyDashboard) {
  return Boolean(
    dashboard?.summaries.some((summary) => summary.status === "pending") ||
    dashboard?.recent_tasks.some(taxonomyTaskIsActive)
  );
}

function getLatestImportTask(tasks?: TaxonomyTaggingTask[]) {
  return tasks?.find((task) =>
    [
      "pending",
      "running",
      "completed_with_errors",
      "complete",
      "failed",
    ].includes(task.status)
  );
}

function getVersionChangeReason(version: TaxonomyVersion) {
  return version.change_reason?.trim() || null;
}

function getVersionStatusLabel(status: TaxonomyVersion["status"]) {
  switch (status) {
    case "active":
      return "生效中";
    case "draft":
      return "草稿";
    case "superseded":
      return "已替换";
    case "deprecated":
      return "已废弃";
    default:
      return status;
  }
}

function getVersionSourceLabel(source: TaxonomyVersion["source"]) {
  switch (source) {
    case "ai_generated":
      return "AI 生成";
    case "default_template":
      return "默认模板";
    case "manual":
      return "手动维护";
    case "tagging_optimization":
      return "打标优化";
    default:
      return source;
  }
}

function getVersionHistoryDescription(version: TaxonomyVersion) {
  return [
    getVersionChangeReason(version),
    version.change_summary,
    formatDate(version.created_at),
  ]
    .filter(Boolean)
    .join(" · ");
}

function SpinningLoaderIcon(props: IconProps) {
  return (
    <SvgLoader
      {...props}
      className={[props.className, "animate-spin"].filter(Boolean).join(" ")}
    />
  );
}

function getArticleLabelStatusLabel(
  status: DocumentTaxonomySummary["current_label_status"]
) {
  switch (status) {
    case "active":
      return "已打标签";
    case "needs_review":
      return "待复核";
    case "needs_retag":
      return "需重新打标";
    case "depends_on_disabled_label":
      return "标签不可用";
    case "tagging_failed":
      return "打标签失败";
    case null:
    case undefined:
      return "标签待生成";
    default:
      return status;
  }
}

function getArticleStage(
  summary: DocumentTaxonomySummary,
  options: { hasActiveTaggingTask?: boolean } = {}
): ArticleStage {
  if (summary.status === "failed") {
    return {
      title: "总结失败",
      description: summary.failure_reason || "需要重新处理摘要",
      progress: 20,
      color: "amber" as const,
    };
  }

  if (summary.status !== "complete") {
    return {
      title: "正在总结",
      description: "大模型正在生成文章 Summary",
      progress: 35,
      color: "blue" as const,
    };
  }

  switch (summary.current_label_status) {
    case "active":
      return {
        title: getArticleLabelStatusLabel(summary.current_label_status),
        description: "文章摘要和标签已生成",
        progress: 100,
        color: "green" as const,
      };
    case "needs_review":
      return {
        title: getArticleLabelStatusLabel(summary.current_label_status),
        description: "标签已生成，需要人工复核",
        progress: 100,
        color: "amber" as const,
      };
    case "needs_retag":
      return {
        title: getArticleLabelStatusLabel(summary.current_label_status),
        description: "摘要已生成，标签需要重新生成",
        progress: 85,
        color: "amber" as const,
      };
    case "depends_on_disabled_label":
      return {
        title: getArticleLabelStatusLabel(summary.current_label_status),
        description: "当前标签依赖已停用节点",
        progress: 85,
        color: "amber" as const,
      };
    case "tagging_failed":
      return {
        title: getArticleLabelStatusLabel(summary.current_label_status),
        description: "标签生成失败，需要人工处理",
        progress: 100,
        color: "amber" as const,
      };
    case null:
    case undefined:
      break;
    default:
      return {
        title: summary.current_label_status,
        description: "文章摘要和标签状态已更新",
        progress: 100,
        color: "green" as const,
      };
  }

  if (!options.hasActiveTaggingTask) {
    return {
      title: "未匹配标签",
      description: "摘要已生成，未匹配到可用标签",
      progress: 100,
      color: "gray" as const,
    };
  }

  return {
    title: "等待打标签",
    description: "摘要已生成，等待标签任务处理",
    progress: 65,
    color: "gray" as const,
  };
}

function getArticleLabelStatusTag(summary: DocumentTaxonomySummary) {
  if (summary.status !== "complete") {
    return {
      title: getArticleLabelStatusLabel(summary.current_label_status),
      color: "gray" as const,
    };
  }

  const stage = getArticleStage(summary);
  return {
    title: stage.title,
    color: stage.color,
  };
}

function getDocumentTitle(summary: DocumentTaxonomySummary) {
  return (
    summary.source_file_name?.trim() ||
    summary.semantic_id?.trim() ||
    "未命名文章"
  );
}

function getArticleFileName(summary: DocumentTaxonomySummary) {
  return summary.source_file_name?.trim() || "";
}

function getArticleFileExtension(summary: DocumentTaxonomySummary) {
  const fileName = getArticleFileName(summary).toLowerCase();
  const match = fileName.match(/\.([a-z0-9]+)$/);
  return match?.[1] ?? "";
}

function getArticleOriginalKind(summary: DocumentTaxonomySummary) {
  const extension = getArticleFileExtension(summary);
  if (extension === "pdf") {
    return "pdf" as const;
  }
  if (extension === "md" || extension === "markdown") {
    return "markdown" as const;
  }
  return "unsupported" as const;
}

function canPreviewArticleOriginal(summary: DocumentTaxonomySummary) {
  return (
    Boolean(getArticleFileName(summary)) &&
    getArticleOriginalKind(summary) !== "unsupported"
  );
}

function createEmptyTaxonomyNode(
  level: TaxonomyNode["level"],
  sortOrder: number
): TaxonomyNode {
  return {
    level,
    name:
      level === "l1"
        ? "新的一级标签"
        : level === "l2"
          ? "新的二级标签"
          : "新的三级标签",
    definition: "",
    applicability: "",
    exclusion: null,
    positive_examples: [],
    negative_examples: [],
    keywords: [],
    synonyms: [],
    source: "manual",
    status: "draft",
    sort_order: sortOrder,
    children: [],
  };
}

function stringifyTaxonomyNodes(nodes: TaxonomyNode[]) {
  return JSON.stringify(nodes, null, 2);
}

function parseTaxonomyNodesJson(value: string): TaxonomyNode[] {
  const parsed = JSON.parse(value) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error("JSON 内容必须是 Taxonomy 节点数组");
  }
  return parsed as TaxonomyNode[];
}

function getRequiredTaxonomyNodeFields(level: TaxonomyNode["level"]) {
  const fields = ["名称", "释义", "适用范围", "关键词"];
  if (level === "leaf") {
    fields.push("正例", "反例");
  }
  return fields;
}

function validateTaxonomyNodeFields(
  node: TaxonomyNode,
  path: string[] = []
): string[] {
  const labelPath = [...path, node.name || "未命名标签"];
  const label = labelPath.join(" / ");
  const errors: string[] = [];

  if (!node.name.trim()) {
    errors.push(`${label}: 名称为必填`);
  }
  if (!node.definition.trim()) {
    errors.push(`${label}: 释义为必填`);
  }
  if (!node.applicability.trim()) {
    errors.push(`${label}: 适用范围为必填`);
  }
  if (!normalizeTaxonomyList(node.keywords).length) {
    errors.push(`${label}: 关键词至少填写 1 个`);
  }
  if (node.level === "leaf") {
    if (!normalizeTaxonomyList(node.positive_examples).length) {
      errors.push(`${label}: 正例至少填写 1 个`);
    }
    if (!normalizeTaxonomyList(node.negative_examples).length) {
      errors.push(`${label}: 反例至少填写 1 个`);
    }
  }

  return errors;
}

function validateTaxonomyNodeTree(
  node: TaxonomyNode,
  path: string[] = []
): string[] {
  const labelPath = [...path, node.name || "未命名标签"];
  const label = labelPath.join(" / ");
  const errors = validateTaxonomyNodeFields(node, path);

  if (node.level !== "leaf" && !node.children.length) {
    errors.push(`${label}: 非三级标签必须包含子标签`);
  }
  node.children.forEach((child) => {
    errors.push(...validateTaxonomyNodeTree(child, labelPath));
  });

  return errors;
}

function validateTaxonomyNodes(nodes: TaxonomyNode[]) {
  return nodes.flatMap((node) => validateTaxonomyNodeTree(node));
}

function getTaxonomyValidationMessage(errors: string[]) {
  if (!errors.length) {
    return null;
  }
  const visibleErrors = errors.slice(0, 5).join("；");
  const hiddenCount = errors.length - 5;
  return hiddenCount > 0
    ? `${visibleErrors}；另有 ${hiddenCount} 个问题`
    : visibleErrors;
}

function normalizeTaxonomyNode(node: TaxonomyNode): TaxonomyNode {
  return {
    ...node,
    name: node.name.trim(),
    definition: node.definition.trim(),
    applicability: node.applicability.trim(),
    exclusion: normalizeOptionalText(node.exclusion),
    keywords: normalizeTaxonomyList(node.keywords),
    synonyms: normalizeTaxonomyList(node.synonyms),
    positive_examples: normalizeTaxonomyList(node.positive_examples),
    negative_examples: normalizeTaxonomyList(node.negative_examples),
    tagging_guidance: normalizeOptionalText(node.tagging_guidance),
    conflict_rules: normalizeOptionalText(node.conflict_rules),
    children: node.children.map(normalizeTaxonomyNode),
  };
}

function normalizeTaxonomyNodes(nodes: TaxonomyNode[]) {
  return nodes.map(normalizeTaxonomyNode);
}

function nextChildLevel(
  level: TaxonomyNode["level"]
): TaxonomyNode["level"] | null {
  if (level === "l1") {
    return "l2";
  }
  if (level === "l2") {
    return "leaf";
  }
  return null;
}

function updateTaxonomyNodeAtPath(
  nodes: TaxonomyNode[],
  path: number[],
  updater: (node: TaxonomyNode) => TaxonomyNode
): TaxonomyNode[] {
  const [targetIndex, ...restPath] = path;
  return nodes.map((node, index) => {
    if (index !== targetIndex) {
      return node;
    }
    if (!restPath.length) {
      return updater(node);
    }
    return {
      ...node,
      children: updateTaxonomyNodeAtPath(node.children, restPath, updater),
    };
  });
}

function removeTaxonomyNodeAtPath(
  nodes: TaxonomyNode[],
  path: number[]
): TaxonomyNode[] {
  const [targetIndex, ...restPath] = path;
  if (!restPath.length) {
    return nodes.filter((_, index) => index !== targetIndex);
  }
  return nodes.map((node, index) =>
    index === targetIndex
      ? {
          ...node,
          children: removeTaxonomyNodeAtPath(node.children, restPath),
        }
      : node
  );
}

function TaxonomyPageLayout({
  route,
  description,
  rightChildren,
  backButton,
  backButtonLabel,
  onBack,
  width = "lg",
  children,
}: {
  route: AdminRouteEntry;
  description: string;
  rightChildren?: ReactNode;
  backButton?: boolean;
  backButtonLabel?: string;
  onBack?: () => void;
  width?: "lg" | "full";
  children: ReactNode;
}) {
  return (
    <SettingsLayouts.Root width={width}>
      <SettingsLayouts.Header
        icon={route.icon}
        title={route.title}
        description={description}
        rightChildren={rightChildren}
        backButton={backButton}
        backButtonLabel={backButtonLabel}
        onBack={onBack}
        divider
      />
      <SettingsLayouts.Body>{children}</SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}

function useTaxonomyDashboard(shouldPoll = false) {
  const { data: dashboard } = useSWR<TaxonomyDashboard>(
    SWR_KEYS.taxonomyDashboard,
    errorHandlingFetcher,
    {
      refreshInterval: (latestData) =>
        shouldPoll || taxonomyDashboardHasActiveProcessing(latestData)
          ? TAXONOMY_DASHBOARD_POLL_INTERVAL_MS
          : 0,
    }
  );
  return dashboard;
}

function useTaxonomyVersions() {
  const { data: versions = [] } = useSWR<TaxonomyVersion[]>(
    SWR_KEYS.taxonomyVersions,
    errorHandlingFetcher
  );
  return versions;
}

function useTaxonomyGenerationConfig() {
  const { data, mutate: mutateConfig } = useSWR<TaxonomyGenerationConfig>(
    SWR_KEYS.taxonomyGenerationConfig,
    fetchTaxonomyGenerationConfig
  );
  return { config: data, mutateConfig };
}

function useDocumentTaxonomyTags(documentId: string) {
  const { data: tags = [] } = useSWR<DocumentTaxonomyTag[]>(
    documentId ? SWR_KEYS.taxonomyDocumentTags(documentId) : null,
    () => fetchDocumentTaxonomyTags(documentId)
  );
  return tags;
}

function StatCard({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail: string;
}) {
  return (
    <Card border="solid" rounding="lg">
      <Section gap={0.25}>
        <Text font="secondary-body" color="text-03">
          {title}
        </Text>
        <Text font="heading-h3" color="text-05">
          {value}
        </Text>
        <Text font="secondary-body" color="text-03" maxLines={2}>
          {detail}
        </Text>
      </Section>
    </Card>
  );
}

function FormGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-3 md:grid-cols-2">{children}</div>;
}

function FullWidthField({ children }: { children: ReactNode }) {
  return <div className="md:col-span-2">{children}</div>;
}

function NodeBadge({ node }: { node: TaxonomyNode }) {
  if (node.level === "leaf") {
    return <Tag title="三级" color="green" />;
  }
  if (node.level === "l2") {
    return <Tag title="二级" color="blue" />;
  }
  return <Tag title="一级" color="gray" />;
}

function getTaxonomyNodeKey(node: TaxonomyNode, path: number[]): string {
  return node.id || `${path.join(".")}-${node.level}-${node.name}`;
}

function buildTreeData(
  nodes: TaxonomyNode[],
  path: number[] = []
): TaxonomyTreeDataNode[] {
  return nodes.map((node, index) => {
    const nodePath = [...path, index];
    const children = buildTreeData(node.children, nodePath);
    const leafIds =
      node.level === "leaf"
        ? node.id
          ? [node.id]
          : []
        : children.flatMap((child) => child.leafIds);

    return {
      key: getTaxonomyNodeKey(node, nodePath),
      title: node.name,
      path: nodePath,
      disableCheckbox: leafIds.length === 0,
      isLeaf: children.length === 0,
      taxonomyNode: node,
      leafIds,
      children,
    };
  });
}

function flattenTreeDataKeys(nodes: TaxonomyTreeDataNode[]): string[] {
  return nodes.flatMap((node) => [
    node.key,
    ...flattenTreeDataKeys(node.children),
  ]);
}

function getExpandableTreeKeys(nodes: TaxonomyTreeDataNode[]): string[] {
  return nodes.flatMap((node) =>
    node.children.length
      ? [node.key, ...getExpandableTreeKeys(node.children)]
      : []
  );
}

function getSelectionState(
  nodes: TaxonomyTreeDataNode[],
  selectedLeafIds: Set<string>
): TaxonomyTreeSelectionState {
  const checkedKeys: string[] = [];
  const halfCheckedKeys: string[] = [];

  const visit = (node: TaxonomyTreeDataNode) => {
    node.children.forEach(visit);

    if (node.taxonomyNode.level === "leaf") {
      if (node.taxonomyNode.id && selectedLeafIds.has(node.taxonomyNode.id)) {
        checkedKeys.push(node.key);
      }
      return;
    }

    const selectedCount = node.leafIds.filter((leafId) =>
      selectedLeafIds.has(leafId)
    ).length;

    if (node.leafIds.length > 0 && selectedCount === node.leafIds.length) {
      checkedKeys.push(node.key);
    } else if (selectedCount > 0) {
      halfCheckedKeys.push(node.key);
    }
  };

  nodes.forEach(visit);
  return { checkedKeys, halfCheckedKeys };
}

function getTaxonomyLevelLabel(level: TaxonomyNode["level"]) {
  if (level === "l1") {
    return "一级";
  }
  if (level === "l2") {
    return "二级";
  }
  return "三级";
}

function TaxonomyTreeNodeTitle({
  node,
  path,
  onEditNode,
  onAddChild,
  onRequestRemove,
}: {
  node: TaxonomyNode;
  path: number[];
  onEditNode?: (path: number[], node: TaxonomyNode) => void;
  onAddChild?: (path: number[], parent: TaxonomyNode) => void;
  onRequestRemove?: (path: number[], node: TaxonomyNode) => void;
}) {
  const childLevel = nextChildLevel(node.level);
  const hoverGroup = `taxonomy-node-${path.join("-")}`;
  const hasActions = !!onRequestRemove || (!!childLevel && !!onAddChild);
  const openEdit = () => onEditNode?.(path, node);

  return (
    <Hoverable.Root group={hoverGroup} width="full">
      <div
        className={`flex min-w-0 items-start justify-between gap-2 py-1.5 pr-2 ${
          onEditNode ? "cursor-pointer" : ""
        }`}
        data-testid={`taxonomy-node-${node.name}`}
        role={onEditNode ? "button" : undefined}
        tabIndex={onEditNode ? 0 : undefined}
        aria-label={onEditNode ? `编辑标签 ${node.name}` : undefined}
        onClick={onEditNode ? openEdit : undefined}
        onKeyDown={
          onEditNode
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  openEdit();
                }
              }
            : undefined
        }
      >
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <Text font="main-ui-action" color="text-05" maxLines={1}>
              {node.name}
            </Text>
            <NodeBadge node={node} />
          </div>
          <Text as="p" font="secondary-body" color="text-03" maxLines={1}>
            {node.definition}
          </Text>
        </div>
        {hasActions && (
          <Hoverable.Item group={hoverGroup} variant="appear-on-hover">
            <div className="flex shrink-0 items-center gap-1 pt-0.5">
              {childLevel && onAddChild && (
                <Button
                  aria-label={`新增${getTaxonomyLevelLabel(childLevel)}标签`}
                  icon={SvgPlus}
                  prominence="tertiary"
                  size="2xs"
                  tooltip={`新增${getTaxonomyLevelLabel(childLevel)}标签`}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onAddChild(path, node);
                  }}
                />
              )}
              {onRequestRemove && (
                <Button
                  aria-label="删除标签"
                  icon={SvgTrash}
                  prominence="tertiary"
                  size="2xs"
                  tooltip="删除"
                  variant="danger"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onRequestRemove(path, node);
                  }}
                />
              )}
            </div>
          </Hoverable.Item>
        )}
      </div>
    </Hoverable.Root>
  );
}

function TaxonomyTreeSwitcherIcon(props: TreeNodeProps) {
  if (props.isLeaf) {
    return <span className="block h-4 w-4" aria-hidden="true" />;
  }

  return (
    <SvgChevronRight
      className={`h-4 w-4 text-text-03 transition-transform ${
        props.expanded ? "rotate-90" : ""
      }`}
    />
  );
}

function TaxonomyTree({
  nodes,
  emptyMessage = "暂无标签节点",
  selectedLeafIds,
  onToggleLeaf,
  onEditNode,
  onAddChild,
  onRequestRemove,
  selectable = false,
}: {
  nodes: TaxonomyNode[];
  emptyMessage?: string;
  selectedLeafIds?: Set<string>;
  onToggleLeaf?: (leafId: string, checked: boolean) => void;
  onEditNode?: (path: number[], node: TaxonomyNode) => void;
  onAddChild?: (path: number[], parent: TaxonomyNode) => void;
  onRequestRemove?: (path: number[], node: TaxonomyNode) => void;
  selectable?: boolean;
}) {
  const treeData = useMemo(() => buildTreeData(nodes), [nodes]);
  const defaultExpandedKeys = useMemo(
    () => getExpandableTreeKeys(treeData),
    [treeData]
  );
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);

  useEffect(() => {
    setExpandedKeys(defaultExpandedKeys);
  }, [defaultExpandedKeys]);

  const selectedIds = selectedLeafIds ?? new Set<string>();
  const { checkedKeys, halfCheckedKeys } = useMemo(
    () => getSelectionState(treeData, selectedIds),
    [treeData, selectedIds]
  );
  const allTreeKeys = useMemo(
    () => new Set(flattenTreeDataKeys(treeData)),
    [treeData]
  );

  const handleCheck: TreeProps<TaxonomyTreeDataNode>["onCheck"] = (
    _checked,
    info
  ) => {
    const target = info.node;
    const leafIds =
      target.taxonomyNode.level === "leaf" && target.taxonomyNode.id
        ? [target.taxonomyNode.id]
        : target.leafIds;

    leafIds.forEach((leafId) => onToggleLeaf?.(leafId, info.checked));
  };

  if (!nodes.length) {
    return (
      <div className="flex items-center justify-center py-5">
        <Text font="secondary-body" color="text-03">
          {emptyMessage}
        </Text>
      </div>
    );
  }

  return (
    <div className="taxonomy-tree w-full rounded-08 border border-border-01 bg-background-tint-00 p-2">
      <Tree<TaxonomyTreeDataNode>
        prefixCls="rc-tree"
        treeData={treeData}
        expandedKeys={expandedKeys}
        checkedKeys={{ checked: checkedKeys, halfChecked: halfCheckedKeys }}
        checkable={selectable}
        checkStrictly
        selectable={false}
        showIcon={false}
        switcherIcon={TaxonomyTreeSwitcherIcon}
        virtual={false}
        onExpand={(nextExpandedKeys) =>
          setExpandedKeys(
            nextExpandedKeys.map(String).filter((key) => allTreeKeys.has(key))
          )
        }
        onCheck={handleCheck}
        titleRender={(treeNode) => (
          <TaxonomyTreeNodeTitle
            node={treeNode.taxonomyNode}
            path={treeNode.path}
            onEditNode={onEditNode}
            onAddChild={onAddChild}
            onRequestRemove={onRequestRemove}
          />
        )}
      />
    </div>
  );
}

const taxonomyJsonEditorTheme = EditorView.theme({
  "&": {
    backgroundColor: "var(--background-neutral-00)",
    color: "var(--text-04)",
    fontSize: "0.875rem",
  },
  ".cm-scroller": {
    fontFamily:
      "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    lineHeight: "1.55",
  },
  ".cm-content": {
    padding: "0.75rem 0",
  },
  ".cm-line": {
    padding: "0 0.75rem",
  },
  ".cm-gutters": {
    backgroundColor: "var(--background-tint-01)",
    borderRight: "1px solid var(--border-02)",
    color: "var(--text-03)",
  },
  ".cm-activeLine": {
    backgroundColor: "var(--background-tint-01)",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "var(--background-tint-02)",
  },
  ".cm-selectionBackground": {
    backgroundColor: "var(--highlight-selection) !important",
  },
  ".cm-focused": {
    outline: "none",
  },
  ".cm-tooltip": {
    backgroundColor: "var(--background-tint-00)",
    border: "1px solid var(--border-02)",
    borderRadius: "0.5rem",
    boxShadow: "var(--shadow-lg)",
    color: "var(--text-04)",
  },
});

const taxonomyJsonEditorExtensions: Extension[] = [
  json(),
  linter(jsonParseLinter(), { delay: 250 }),
  lintGutter(),
  taxonomyJsonEditorTheme,
];

function TaxonomyJsonEditor({
  value,
  error,
  onChange,
}: {
  value: string;
  error: string | null;
  onChange: (value: string) => void;
}) {
  const lineCount = value.split("\n").length;

  return (
    <div className="w-full overflow-hidden rounded-12 border border-border-02 bg-background-neutral-00">
      <div className="flex items-center justify-between gap-3 border-b border-border-02 bg-background-tint-01 px-3 py-2">
        <div className="flex items-center gap-2">
          <Tag
            title={error ? "JSON 需要修正" : "JSON 有效"}
            color={error ? "amber" : "green"}
            size="sm"
          />
          <Text font="secondary-body" color="text-03">
            {`${lineCount} 行`}
          </Text>
        </div>
      </div>
      <CodeMirror
        data-testid="taxonomy-json-editor"
        value={value}
        width="100%"
        minHeight="36rem"
        maxHeight="54rem"
        basicSetup={{
          bracketMatching: true,
          closeBrackets: true,
          foldGutter: true,
          highlightActiveLine: true,
          highlightActiveLineGutter: true,
          lineNumbers: true,
          syntaxHighlighting: true,
        }}
        extensions={taxonomyJsonEditorExtensions}
        indentWithTab
        onChange={onChange}
        theme="light"
      />
    </div>
  );
}

function TaxonomyAddNodeModal({
  target,
  onClose,
  onConfirm,
}: {
  target: TaxonomyAddNodeTarget | null;
  onClose: () => void;
  onConfirm: (node: TaxonomyNode) => void;
}) {
  const [draftNode, setDraftNode] = useState<TaxonomyNode | null>(null);

  useEffect(() => {
    if (!target) {
      return;
    }
    setDraftNode({
      ...createEmptyTaxonomyNode(target.level, 0),
      name: "",
    });
  }, [target]);

  if (!target || !draftNode) {
    return null;
  }

  const levelLabel = getTaxonomyLevelLabel(target.level);
  const validationErrors = validateTaxonomyNodeFields(draftNode);
  const validationMessage = getTaxonomyValidationMessage(validationErrors);
  const requiredFields = getRequiredTaxonomyNodeFields(draftNode.level).join(
    "、"
  );
  const canConfirm = validationErrors.length === 0;

  const updateField = <K extends keyof TaxonomyNode>(
    key: K,
    value: TaxonomyNode[K]
  ) => {
    setDraftNode((current) =>
      current ? { ...current, [key]: value } : current
    );
  };

  const updateListField = (key: TaxonomyNodeListField, value: string) => {
    updateField(key, parseTaxonomyList(value));
  };

  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <Modal.Content width="sm" height="lg">
        <Modal.Header
          icon={SvgPlus}
          title={`新增${levelLabel}标签`}
          description={
            target.parentNode ? `上级：${target.parentNode.name}` : undefined
          }
          onClose={onClose}
        />
        <Modal.Body>
          <Section gap={0.75} alignItems="stretch" justifyContent="start">
            <MessageCard
              title="字段规则"
              description={`必填：${requiredFields}。可选：同义词、排除说明、打标指引、冲突规则。`}
              padding="xs"
            />
            {validationMessage && (
              <MessageCard
                title="请补全必填字段"
                description={validationMessage}
                padding="xs"
              />
            )}
            <InputVertical title="名称" suffix="必填" withLabel>
              <InputTypeIn
                value={draftNode.name}
                onChange={(event) => updateField("name", event.target.value)}
                showClearButton={false}
              />
            </InputVertical>
            <InputVertical title="释义" suffix="必填" withLabel>
              <InputTextArea
                value={draftNode.definition}
                onChange={(event) =>
                  updateField("definition", event.target.value)
                }
                rows={3}
                maxRows={8}
                autoResize
              />
            </InputVertical>
            <InputVertical title="适用范围" suffix="必填" withLabel>
              <InputTextArea
                value={draftNode.applicability}
                onChange={(event) =>
                  updateField("applicability", event.target.value)
                }
                rows={2}
                maxRows={6}
                autoResize
              />
            </InputVertical>
            <InputVertical
              title="关键词"
              suffix="必填"
              description="用逗号或换行分隔"
              withLabel
            >
              <InputTextArea
                value={draftNode.keywords.join(", ")}
                onChange={(event) =>
                  updateListField("keywords", event.target.value)
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
            <InputVertical
              title="同义词"
              suffix="可选"
              description="用逗号或换行分隔"
              withLabel
            >
              <InputTextArea
                value={draftNode.synonyms.join(", ")}
                onChange={(event) =>
                  updateListField("synonyms", event.target.value)
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
            {draftNode.level === "leaf" && (
              <FormGrid>
                <InputVertical
                  title="正例"
                  suffix="必填"
                  description="该标签应该命中的典型文章"
                  withLabel
                >
                  <InputTextArea
                    value={draftNode.positive_examples.join("\n")}
                    onChange={(event) =>
                      updateListField("positive_examples", event.target.value)
                    }
                    rows={2}
                    maxRows={6}
                    autoResize
                  />
                </InputVertical>
                <InputVertical
                  title="反例"
                  suffix="必填"
                  description="容易混淆但不应命中的文章"
                  withLabel
                >
                  <InputTextArea
                    value={draftNode.negative_examples.join("\n")}
                    onChange={(event) =>
                      updateListField("negative_examples", event.target.value)
                    }
                    rows={2}
                    maxRows={6}
                    autoResize
                  />
                </InputVertical>
              </FormGrid>
            )}
            <InputVertical title="排除说明" suffix="可选" withLabel>
              <InputTextArea
                value={draftNode.exclusion ?? ""}
                onChange={(event) =>
                  updateField(
                    "exclusion",
                    normalizeOptionalText(event.target.value)
                  )
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
            <InputVertical title="打标指引" suffix="可选" withLabel>
              <InputTextArea
                value={draftNode.tagging_guidance ?? ""}
                onChange={(event) =>
                  updateField(
                    "tagging_guidance",
                    normalizeOptionalText(event.target.value)
                  )
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
            <InputVertical title="冲突规则" suffix="可选" withLabel>
              <InputTextArea
                value={draftNode.conflict_rules ?? ""}
                onChange={(event) =>
                  updateField(
                    "conflict_rules",
                    normalizeOptionalText(event.target.value)
                  )
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
          </Section>
        </Modal.Body>
        <Modal.Footer>
          <Button prominence="secondary" onClick={onClose}>
            取消
          </Button>
          <Button
            icon={SvgCheck}
            prominence="primary"
            onClick={() => onConfirm(normalizeTaxonomyNode(draftNode))}
            disabled={!canConfirm}
          >
            确定
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

function TaxonomyEditNodeModal({
  target,
  onClose,
  onConfirm,
}: {
  target: TaxonomyNodeActionTarget | null;
  onClose: () => void;
  onConfirm: (node: TaxonomyNode) => void;
}) {
  const [draftNode, setDraftNode] = useState<TaxonomyNode | null>(null);

  useEffect(() => {
    if (!target) {
      return;
    }
    setDraftNode({
      ...target.node,
      positive_examples: [...target.node.positive_examples],
      negative_examples: [...target.node.negative_examples],
      keywords: [...target.node.keywords],
      synonyms: [...target.node.synonyms],
      children: target.node.children,
    });
  }, [target]);

  if (!target || !draftNode) {
    return null;
  }

  const updateField = <K extends keyof TaxonomyNode>(
    key: K,
    value: TaxonomyNode[K]
  ) => {
    setDraftNode((current) =>
      current ? { ...current, [key]: value } : current
    );
  };

  const updateListField = (key: TaxonomyNodeListField, value: string) => {
    updateField(key, parseTaxonomyList(value));
  };

  const validationErrors = validateTaxonomyNodeFields(draftNode);
  const validationMessage = getTaxonomyValidationMessage(validationErrors);
  const requiredFields = getRequiredTaxonomyNodeFields(draftNode.level).join(
    "、"
  );
  const canConfirm = validationErrors.length === 0;

  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <Modal.Content width="sm" height="lg">
        <Modal.Header
          icon={SvgEdit}
          title="编辑标签"
          description={getTaxonomyLevelLabel(draftNode.level)}
          onClose={onClose}
        />
        <Modal.Body>
          <Section gap={0.75} alignItems="stretch" justifyContent="start">
            <MessageCard
              title="字段规则"
              description={`必填：${requiredFields}。可选：同义词、排除说明、打标指引、冲突规则。`}
              padding="xs"
            />
            {validationMessage && (
              <MessageCard
                title="请补全必填字段"
                description={validationMessage}
                padding="xs"
              />
            )}
            <InputVertical title="名称" suffix="必填" withLabel>
              <InputTypeIn
                value={draftNode.name}
                onChange={(event) => updateField("name", event.target.value)}
                showClearButton={false}
              />
            </InputVertical>
            <InputVertical title="释义" suffix="必填" withLabel>
              <InputTextArea
                value={draftNode.definition}
                onChange={(event) =>
                  updateField("definition", event.target.value)
                }
                rows={3}
                maxRows={8}
                autoResize
              />
            </InputVertical>
            <InputVertical title="适用范围" suffix="必填" withLabel>
              <InputTextArea
                value={draftNode.applicability}
                onChange={(event) =>
                  updateField("applicability", event.target.value)
                }
                rows={2}
                maxRows={6}
                autoResize
              />
            </InputVertical>
            <InputVertical
              title="关键词"
              suffix="必填"
              description="用逗号或换行分隔"
              withLabel
            >
              <InputTextArea
                value={draftNode.keywords.join(", ")}
                onChange={(event) =>
                  updateListField("keywords", event.target.value)
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
            <InputVertical
              title="同义词"
              suffix="可选"
              description="用逗号或换行分隔"
              withLabel
            >
              <InputTextArea
                value={draftNode.synonyms.join(", ")}
                onChange={(event) =>
                  updateListField("synonyms", event.target.value)
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
            {draftNode.level === "leaf" && (
              <FormGrid>
                <InputVertical title="正例" suffix="必填" withLabel>
                  <InputTextArea
                    value={draftNode.positive_examples.join("\n")}
                    onChange={(event) =>
                      updateListField("positive_examples", event.target.value)
                    }
                    rows={2}
                    maxRows={6}
                    autoResize
                  />
                </InputVertical>
                <InputVertical title="反例" suffix="必填" withLabel>
                  <InputTextArea
                    value={draftNode.negative_examples.join("\n")}
                    onChange={(event) =>
                      updateListField("negative_examples", event.target.value)
                    }
                    rows={2}
                    maxRows={6}
                    autoResize
                  />
                </InputVertical>
              </FormGrid>
            )}
            <InputVertical title="排除说明" suffix="可选" withLabel>
              <InputTextArea
                value={draftNode.exclusion ?? ""}
                onChange={(event) =>
                  updateField(
                    "exclusion",
                    normalizeOptionalText(event.target.value)
                  )
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
            <InputVertical title="打标指引" suffix="可选" withLabel>
              <InputTextArea
                value={draftNode.tagging_guidance ?? ""}
                onChange={(event) =>
                  updateField(
                    "tagging_guidance",
                    normalizeOptionalText(event.target.value)
                  )
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
            <InputVertical title="冲突规则" suffix="可选" withLabel>
              <InputTextArea
                value={draftNode.conflict_rules ?? ""}
                onChange={(event) =>
                  updateField(
                    "conflict_rules",
                    normalizeOptionalText(event.target.value)
                  )
                }
                rows={2}
                maxRows={5}
                autoResize
              />
            </InputVertical>
          </Section>
        </Modal.Body>
        <Modal.Footer>
          <Button prominence="secondary" onClick={onClose}>
            取消
          </Button>
          <Button
            icon={SvgCheck}
            prominence="primary"
            onClick={() => onConfirm(normalizeTaxonomyNode(draftNode))}
            disabled={!canConfirm}
          >
            保存
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

function TaxonomyDeleteConfirmModal({
  target,
  onClose,
  onConfirm,
}: {
  target: TaxonomyNodeActionTarget | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  if (!target) {
    return null;
  }

  const hasChildren = target.node.children.length > 0;

  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <Modal.Content width="sm" height="fit">
        <Modal.Header icon={SvgTrash} title="删除标签" onClose={onClose} />
        <Modal.Body>
          <Text as="p" font="main-ui-body" color="text-04">
            {hasChildren
              ? `确定删除「${target.node.name}」及其所有下级标签吗？`
              : `确定删除「${target.node.name}」吗？`}
          </Text>
        </Modal.Body>
        <Modal.Footer>
          <Button prominence="secondary" onClick={onClose}>
            取消
          </Button>
          <Button
            icon={SvgTrash}
            prominence="primary"
            variant="danger"
            onClick={onConfirm}
          >
            删除
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

function TaxonomyBuilder({ versions }: { versions: TaxonomyVersion[] }) {
  const [taxonomyNodes, setTaxonomyNodes] = useState<TaxonomyNode[]>([]);
  const [taxonomyJson, setTaxonomyJson] = useState("[]");
  const [hydratedVersionId, setHydratedVersionId] = useState<number | null>(
    null
  );
  const [hasLocalTaxonomyChanges, setHasLocalTaxonomyChanges] = useState(false);
  const [generationPrompt, setGenerationPrompt] = useState("");
  const [lastGeneratedPrompt, setLastGeneratedPrompt] = useState<string | null>(
    null
  );
  const [editorView, setEditorView] = useState<"tree" | "json">("tree");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [addNodeTarget, setAddNodeTarget] =
    useState<TaxonomyAddNodeTarget | null>(null);
  const [editNodeTarget, setEditNodeTarget] =
    useState<TaxonomyNodeActionTarget | null>(null);
  const [deleteNodeTarget, setDeleteNodeTarget] =
    useState<TaxonomyNodeActionTarget | null>(null);
  const [changeReason, setChangeReason] = useState("");
  const [pendingVersion, setPendingVersion] = useState<TaxonomyVersion | null>(
    null
  );
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [generationStatus, setGenerationStatus] =
    useState<TaxonomyGenerationStatus | null>(null);
  const [generationConfigOpen, setGenerationConfigOpen] = useState(false);
  const hasRestoredGenerationRef = useRef(false);
  const { config: generationConfig } = useTaxonomyGenerationConfig();

  const latestVersion =
    [pendingVersion, ...versions]
      .filter((version): version is TaxonomyVersion => Boolean(version))
      .sort(
        (left, right) =>
          right.version_number - left.version_number || right.id - left.id
      )[0] ?? null;
  const activeDrafts = versions.filter((version) => version.status === "draft");
  const nodeCounts = countNodes(taxonomyNodes);
  const canSave = taxonomyNodes.length > 0 && taxonomyJson.trim().length > 0;
  const isGeneratingTaxonomy = busyAction === "generate";
  const generationProgress = Math.min(
    100,
    Math.max(0, generationStatus?.progress ?? 0)
  );
  const generationStatusMessage =
    generationStatus?.message ||
    "正在生成三级标签体系，内容会流式填入下方编辑区。";

  useEffect(() => {
    if (!latestVersion || latestVersion.nodes.length === 0) {
      return;
    }
    if (hasLocalTaxonomyChanges || hydratedVersionId === latestVersion.id) {
      return;
    }

    setTaxonomyNodes(latestVersion.nodes);
    setTaxonomyJson(stringifyTaxonomyNodes(latestVersion.nodes));
    setJsonError(null);
    setHydratedVersionId(latestVersion.id);
  }, [hasLocalTaxonomyChanges, hydratedVersionId, latestVersion]);

  const applyNodes = (
    nodes: TaxonomyNode[],
    options: { markChanged?: boolean; versionId?: number | null } = {}
  ) => {
    setTaxonomyNodes(nodes);
    setTaxonomyJson(stringifyTaxonomyNodes(nodes));
    setJsonError(null);
    setHasLocalTaxonomyChanges(options.markChanged ?? true);
    if (options.versionId !== undefined) {
      setHydratedVersionId(options.versionId);
    }
  };

  const runTaxonomyGeneration = useCallback(
    async ({
      prompt,
      config,
      initialNodes = [],
      initialStatus = {
        message: "正在启动标签体系生成",
        progress: 0,
      },
      restored = false,
    }: {
      prompt: string;
      config: TaxonomyGenerationConfig;
      initialNodes?: TaxonomyNode[];
      initialStatus?: TaxonomyGenerationStatus;
      restored?: boolean;
    }) => {
      const trimmedPrompt = prompt.trim();
      if (!trimmedPrompt) {
        toast.error("请先输入标签体系建设提示词");
        return;
      }

      setGenerationPrompt(trimmedPrompt);
      setLastGeneratedPrompt(trimmedPrompt);
      setBusyAction("generate");
      setHasLocalTaxonomyChanges(true);
      setHydratedVersionId(null);
      setTaxonomyNodes(initialNodes);
      setTaxonomyJson(stringifyTaxonomyNodes(initialNodes));
      setJsonError(null);
      setEditorView("tree");
      setGenerationStatus(initialStatus);
      writePersistedTaxonomyGeneration({
        prompt: trimmedPrompt,
        status: initialStatus,
        nodes: initialNodes,
      });
      let latestGeneratedNodes = initialNodes;

      try {
        const nodes = await generateTaxonomyDraftStream(
          {
            company_description: trimmedPrompt,
            organization_context: null,
            knowledge_scope: null,
            classification_preferences: null,
            generation_config: buildTaxonomyGenerationRequestConfig({
              config,
              companyDescription: trimmedPrompt,
            }),
            parallelism: config.third_level_parallelism,
          },
          (event: TaxonomyDraftStreamEvent) => {
            const nextStatus = {
              message: event.message || "正在生成标签体系",
              progress: event.progress ?? 0,
            };
            if (event.nodes) {
              latestGeneratedNodes = event.nodes;
            }
            setGenerationStatus(nextStatus);
            writePersistedTaxonomyGeneration({
              prompt: trimmedPrompt,
              status: nextStatus,
              nodes: latestGeneratedNodes,
            });
            if (event.nodes) {
              applyNodes(event.nodes, { markChanged: true, versionId: null });
              setEditorView("tree");
            }
          }
        );
        applyNodes(nodes);
        setLastGeneratedPrompt(trimmedPrompt);
        setGenerationPrompt("");
        setEditorView("tree");
        clearPersistedTaxonomyGeneration();
        toast.success("标签体系已生成，可以继续编辑完善");
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : "标签体系生成失败"
        );
        if (!restored) {
          clearPersistedTaxonomyGeneration();
        }
      } finally {
        setBusyAction(null);
        setGenerationStatus(null);
      }
    },
    []
  );

  useEffect(() => {
    if (hasRestoredGenerationRef.current) {
      return;
    }

    const persistedGeneration = readPersistedTaxonomyGeneration();
    if (!persistedGeneration) {
      hasRestoredGenerationRef.current = true;
      return;
    }
    if (!generationConfig) {
      return;
    }
    hasRestoredGenerationRef.current = true;

    void runTaxonomyGeneration({
      prompt: persistedGeneration.prompt,
      config: generationConfig,
      initialNodes: persistedGeneration.nodes,
      initialStatus: {
        message: persistedGeneration.status.message || "正在恢复标签体系生成",
        progress: persistedGeneration.status.progress,
      },
      restored: true,
    });
  }, [generationConfig, runTaxonomyGeneration]);

  const handleGenerate = async () => {
    if (!generationConfig) {
      toast.error("生成参数仍在加载，请稍后再试");
      return;
    }
    await runTaxonomyGeneration({
      prompt: generationPrompt,
      config: generationConfig,
    });
  };

  const syncTaxonomyJsonToTree = (
    nextJson: string,
    options: { showToast?: boolean } = {}
  ) => {
    setTaxonomyJson(nextJson);
    setHasLocalTaxonomyChanges(true);

    try {
      const nodes = normalizeTaxonomyNodes(parseTaxonomyNodesJson(nextJson));
      const validationMessage = getTaxonomyValidationMessage(
        validateTaxonomyNodes(nodes)
      );
      if (validationMessage) {
        throw new Error(validationMessage);
      }
      setTaxonomyNodes(nodes);
      setJsonError(null);
      setHydratedVersionId(null);
      return true;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "JSON 内容不完整";
      setJsonError(message);
      if (options.showToast) {
        toast.error(message);
      }
      return false;
    }
  };

  const handleOpenAddRootNode = () => {
    if (
      editorView === "json" &&
      !syncTaxonomyJsonToTree(taxonomyJson, { showToast: true })
    ) {
      return;
    }
    setEditorView("tree");
    setAddNodeTarget({
      parentPath: [],
      level: "l1",
    });
  };

  const handleOpenAddChildNode = (path: number[], parentNode: TaxonomyNode) => {
    const childLevel = nextChildLevel(parentNode.level);
    if (!childLevel) {
      return;
    }
    setAddNodeTarget({
      parentPath: path,
      parentNode,
      level: childLevel,
    });
  };

  const handleConfirmAddNode = (node: TaxonomyNode) => {
    if (!addNodeTarget) {
      return;
    }

    const validationMessage = getTaxonomyValidationMessage(
      validateTaxonomyNodeFields(node)
    );
    if (validationMessage) {
      toast.error(validationMessage);
      return;
    }

    if (!addNodeTarget.parentNode) {
      applyNodes([
        ...taxonomyNodes,
        {
          ...normalizeTaxonomyNode(node),
          sort_order: taxonomyNodes.length,
        },
      ]);
      setEditorView("tree");
      setAddNodeTarget(null);
      return;
    }

    applyNodes(
      updateTaxonomyNodeAtPath(
        taxonomyNodes,
        addNodeTarget.parentPath,
        (current) => ({
          ...current,
          children: [
            ...current.children,
            {
              ...normalizeTaxonomyNode(node),
              sort_order: current.children.length,
            },
          ],
        })
      )
    );
    setAddNodeTarget(null);
  };

  const handleConfirmEditNode = (node: TaxonomyNode) => {
    if (!editNodeTarget) {
      return;
    }
    const normalizedNode = normalizeTaxonomyNode(node);
    const validationMessage = getTaxonomyValidationMessage(
      validateTaxonomyNodeFields(normalizedNode)
    );
    if (validationMessage) {
      toast.error(validationMessage);
      return;
    }
    applyNodes(
      updateTaxonomyNodeAtPath(
        taxonomyNodes,
        editNodeTarget.path,
        () => normalizedNode
      )
    );
    setEditNodeTarget(null);
  };

  const handleConfirmRemoveNode = () => {
    if (!deleteNodeTarget) {
      return;
    }
    applyNodes(removeTaxonomyNodeAtPath(taxonomyNodes, deleteNodeTarget.path));
    setDeleteNodeTarget(null);
  };

  const handleSaveDraft = async () => {
    if (!canSave) {
      toast.error("请先生成、粘贴 JSON 或编辑标签体系");
      return;
    }

    let nodes: TaxonomyNode[];
    try {
      nodes = normalizeTaxonomyNodes(parseTaxonomyNodesJson(taxonomyJson));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "JSON 格式不正确");
      return;
    }
    const validationMessage = getTaxonomyValidationMessage(
      validateTaxonomyNodes(nodes)
    );
    if (validationMessage) {
      toast.error(validationMessage);
      return;
    }

    setBusyAction("save");
    try {
      const version = await createTaxonomyDraft({
        name: "企业知识库标签体系",
        selected_default_leaf_ids: [],
        generated_nodes: nodes,
        company_description: lastGeneratedPrompt || generationPrompt || null,
        change_reason: changeReason.trim() || "手动保存标签体系草稿",
      });
      setPendingVersion(version);
      setHasLocalTaxonomyChanges(false);
      setHydratedVersionId(version.id);
      toast.success(`草稿 v${version.version_number} 已保存`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setBusyAction(null);
    }
  };

  const handleActivate = async (versionId: number) => {
    setBusyAction(`activate-${versionId}`);
    try {
      const version = await activateTaxonomyVersion(versionId);
      setPendingVersion(null);
      toast.success(`标签体系 v${version.version_number} 已生效`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "生效失败");
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <Section
      id="taxonomy-builder"
      className="scroll-mt-24"
      gap={1}
      height="fit"
      justifyContent="start"
    >
      <Card border="solid" rounding="lg" padding="fit">
        <CardLayout.Header>
          <div className="flex w-full items-center justify-between gap-3 px-4 py-3">
            <Content
              icon={SvgSparkle}
              title="标签生成"
              description="输入业务背景后生成三级标签体系，可在生成前调整参数。"
              sizePreset="main-ui"
              variant="section"
            />
            <div className="[&_.interactive-container]:px-2!">
              <Button
                icon={SvgSettings}
                prominence="tertiary"
                size="sm"
                tooltip="调整生成参数"
                onClick={() => setGenerationConfigOpen(true)}
              >
                参数
              </Button>
            </div>
          </div>
        </CardLayout.Header>
        <Divider paddingParallel="fit" paddingPerpendicular="fit" />
        <Section
          className="px-4 pb-4 pt-4"
          gap={0.75}
          alignItems="stretch"
          height="fit"
          justifyContent="start"
        >
          <div className="w-full rounded-12 border border-border-01 bg-background-neutral-00 p-3 transition-colors focus-within:border-border-05 focus-within:shadow-[inset_0_0_0_2px_var(--background-tint-04)]">
            <InputTextArea
              variant="internal"
              value={generationPrompt}
              onChange={(e) => setGenerationPrompt(e.target.value)}
              rows={4}
              maxRows={7}
              autoResize
              resizable={false}
              className="min-h-[5.75rem] min-w-0 bg-transparent p-0 [&_textarea]:!font-main-ui-muted [&_textarea]:leading-5 [&_textarea::placeholder]:!font-main-ui-muted"
              placeholder="例如：我们是一家制造业企业，知识库包含制度流程、质量管理、设备运维、售后维修、产品手册和安全生产文档。重点关注一线员工查找制度、维修手册和质量问题复盘的场景。"
            />
            <div className="mt-3 flex items-center justify-end [&_.interactive-container]:h-10! [&_.interactive-container]:min-w-[6.5rem]! [&_.interactive-container]:rounded-12! [&_.interactive-container]:px-3!">
              <Button
                icon={isGeneratingTaxonomy ? SpinningLoaderIcon : SvgSparkle}
                prominence="primary"
                onClick={handleGenerate}
                disabled={isGeneratingTaxonomy || !generationConfig}
              >
                {isGeneratingTaxonomy ? "生成中" : "生成"}
              </Button>
            </div>
          </div>
          {isGeneratingTaxonomy && (
            <div
              className="rounded-12 border border-border-01 bg-background-tint-01 px-3 py-2"
              aria-live="polite"
              role="status"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <div className="flex size-6 shrink-0 items-center justify-center rounded-08 border border-border-01 bg-background-neutral-00">
                    <SvgLoader className="size-3.5 animate-spin text-text-03" />
                  </div>
                  <Text
                    as="p"
                    font="secondary-body"
                    color="text-04"
                    maxLines={1}
                  >
                    {generationStatusMessage}
                  </Text>
                </div>
                <Text font="secondary-mono-label" color="text-03" nowrap>
                  {`${generationProgress}%`}
                </Text>
              </div>
              <div
                className="mt-2 h-1 overflow-hidden rounded-full bg-background-tint-03"
                aria-hidden
              >
                <div
                  className="h-full rounded-full bg-theme-primary-05 transition-[width] duration-300"
                  style={{ width: `${generationProgress}%` }}
                />
              </div>
            </div>
          )}
        </Section>
      </Card>

      <Card border="solid" rounding="lg">
        <CardLayout.Header>
          <div className="p-2 pb-1.5">
            <Content
              icon={SvgEdit}
              title="标签管理"
              description={`一级 ${nodeCounts.l1} · 二级 ${nodeCounts.l2} · 三级 ${nodeCounts.leaf}`}
              sizePreset="main-ui"
              variant="section"
            />
          </div>
          <div className="flex items-center justify-between gap-2 px-2 pb-2">
            <div className="[&_.interactive-container]:min-w-32! [&_.interactive-container]:px-3!">
              <Button
                icon={SvgPlus}
                prominence="secondary"
                size="sm"
                variant="action"
                onClick={handleOpenAddRootNode}
                disabled={isGeneratingTaxonomy}
              >
                新增一级标签
              </Button>
            </div>
            <div className="flex shrink-0 items-center">
              <div className="inline-flex items-center gap-0.5 rounded-04 border border-border-02 bg-background-neutral-00 p-0.5 [&_.interactive-container]:h-7! [&_.interactive-container]:rounded-04! [&_.interactive-container]:px-2!">
                <Button
                  icon={SvgBranch}
                  prominence={editorView === "tree" ? "secondary" : "tertiary"}
                  aria-pressed={editorView === "tree"}
                  size="xs"
                  onClick={() => setEditorView("tree")}
                >
                  树
                </Button>
                <Button
                  icon={SvgBracketCurly}
                  prominence={editorView === "json" ? "secondary" : "tertiary"}
                  aria-pressed={editorView === "json"}
                  size="xs"
                  onClick={() => setEditorView("json")}
                >
                  JSON
                </Button>
                <div className="mx-0.5 h-4 w-px bg-border-02" aria-hidden />
                <Button
                  href={ADMIN_ROUTES.TAXONOMY_HISTORY.path}
                  icon={SvgClock}
                  prominence="tertiary"
                  size="xs"
                >
                  版本记录
                </Button>
              </div>
            </div>
          </div>
        </CardLayout.Header>
        <Divider paddingParallel="fit" paddingPerpendicular="fit" />
        <div className="p-2">
          {editorView === "tree" ? (
            <Section gap={0.75}>
              <TaxonomyTree
                nodes={taxonomyNodes}
                emptyMessage={
                  isGeneratingTaxonomy ? "正在生成中" : "暂无标签节点"
                }
                onEditNode={(path, node) => setEditNodeTarget({ path, node })}
                onAddChild={handleOpenAddChildNode}
                onRequestRemove={(path, node) =>
                  setDeleteNodeTarget({ path, node })
                }
              />
            </Section>
          ) : (
            <Section gap={0.75} alignItems="stretch">
              {jsonError && (
                <MessageCard
                  title="JSON 校验提示"
                  description={jsonError}
                  padding="xs"
                />
              )}
              <TaxonomyJsonEditor
                value={taxonomyJson}
                error={jsonError}
                onChange={syncTaxonomyJsonToTree}
              />
            </Section>
          )}
        </div>
        <Divider paddingParallel="fit" paddingPerpendicular="fit" />
        <div className="grid gap-2 p-2 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <InputVertical title="本次修改说明（可选）" withLabel>
            <InputTypeIn
              value={changeReason}
              onChange={(e) => setChangeReason(e.target.value)}
              placeholder="例如：新增设备维修相关标签，补充质量复盘场景"
            />
          </InputVertical>
          <Button
            icon={SvgCheck}
            prominence="primary"
            onClick={handleSaveDraft}
            disabled={busyAction === "save" || isGeneratingTaxonomy || !canSave}
          >
            保存草稿
          </Button>
        </div>
        {(pendingVersion || activeDrafts.length > 0) && (
          <>
            <Divider paddingParallel="fit" paddingPerpendicular="fit" />
            <Section gap={0.5}>
              {[pendingVersion, ...activeDrafts]
                .filter(Boolean)
                .filter(
                  (version, index, self) =>
                    self.findIndex((item) => item?.id === version?.id) === index
                )
                .map((version) => (
                  <InputHorizontal
                    key={version!.id}
                    title={`草稿 v${version!.version_number}`}
                    description={
                      getVersionChangeReason(version!) || "未填写修改说明"
                    }
                    withLabel
                  >
                    <Button
                      prominence="tertiary"
                      icon={SvgCheck}
                      onClick={() => handleActivate(version!.id)}
                      disabled={busyAction === `activate-${version!.id}`}
                    >
                      设为生效
                    </Button>
                  </InputHorizontal>
                ))}
            </Section>
          </>
        )}
      </Card>

      <TaxonomyAddNodeModal
        target={addNodeTarget}
        onClose={() => setAddNodeTarget(null)}
        onConfirm={handleConfirmAddNode}
      />
      <TaxonomyEditNodeModal
        target={editNodeTarget}
        onClose={() => setEditNodeTarget(null)}
        onConfirm={handleConfirmEditNode}
      />
      <TaxonomyDeleteConfirmModal
        target={deleteNodeTarget}
        onClose={() => setDeleteNodeTarget(null)}
        onConfirm={handleConfirmRemoveNode}
      />
      <TaxonomyGenerationConfigModal
        open={generationConfigOpen}
        onClose={() => setGenerationConfigOpen(false)}
      />
    </Section>
  );
}

function ArticleTagResultList({ tags }: { tags: DocumentTaxonomyTag[] }) {
  const failedTag = tags.find((tag) => tag.status === "tagging_failed");
  if (failedTag) {
    const failedStatus = (
      <div className="w-fit">
        <Tag title="打标签失败" color="amber" />
      </div>
    );

    return failedTag.unmatched_reason ? (
      <Tooltip tooltip={failedTag.unmatched_reason}>{failedStatus}</Tooltip>
    ) : (
      failedStatus
    );
  }

  const activeTags = tags.filter((tag) => tag.status === "active");
  if (!activeTags.length) {
    return (
      <div className="w-fit">
        <Tag title="暂无标签" color="gray" />
      </div>
    );
  }

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-1.5">
      {activeTags.map((tag) => {
        const title = getDocumentTaxonomyTagTitle(tag);
        const isNew = isTaskGeneratedTag(tag);

        return (
          <div key={tag.id} className="flex min-w-0 items-center gap-1">
            <ArticleTagPill tag={tag} maxWidthClassName="max-w-[15rem]" />
            {isNew && (
              <Tooltip tooltip="本次标签为自检 Agent 新增">
                <NewTagBadge />
              </Tooltip>
            )}
          </div>
        );
      })}
    </div>
  );
}

function getSummaryStatusColor(status: DocumentTaxonomySummary["status"]) {
  if (status === "complete") {
    return "green" as const;
  }
  if (status === "failed") {
    return "amber" as const;
  }
  return "blue" as const;
}

function ProcessingCellIndicator({
  ariaLabel,
  tooltip,
}: {
  ariaLabel: string;
  tooltip: string;
}) {
  return (
    <Tooltip tooltip={tooltip}>
      <div
        aria-label={ariaLabel}
        className="flex size-6 items-center justify-center rounded-04 bg-status-info-01 text-status-info-05"
        role="status"
      >
        <SvgLoader size={14} className="animate-spin" />
      </div>
    </Tooltip>
  );
}

function articleTagsAreProcessing({
  summary,
  hasActiveTaggingTask,
}: {
  summary: DocumentTaxonomySummary;
  hasActiveTaggingTask: boolean;
}) {
  return (
    summary.status === "pending" ||
    (summary.status === "complete" &&
      summary.current_label_status == null &&
      hasActiveTaggingTask)
  );
}

const IMPORTED_ARTICLES_GRID_COLUMNS =
  "3rem minmax(0,1.7fr) 11.5rem 7rem 5rem minmax(12rem,1.25fr) 7.5rem";

function ArticleProgressCell({
  summary,
  hasActiveTaggingTask,
}: {
  summary: DocumentTaxonomySummary;
  hasActiveTaggingTask: boolean;
}) {
  const stage = getArticleStage(summary, { hasActiveTaggingTask });

  return (
    <div className="flex min-w-0 justify-center">
      <Text font="main-ui-action" color="text-05" nowrap>
        {`${stage.progress}%`}
      </Text>
    </div>
  );
}

function ArticleSummaryStatus({
  summary,
}: {
  summary: DocumentTaxonomySummary;
}) {
  if (summary.status === "pending") {
    return (
      <div className="flex min-w-0 items-center justify-center">
        <ProcessingCellIndicator
          ariaLabel="Summary 正在生成"
          tooltip="正在生成 Summary"
        />
      </div>
    );
  }

  return (
    <div className="flex min-w-0 items-center justify-center">
      <Tag
        title={getSummaryStatusLabel(summary.status)}
        color={getSummaryStatusColor(summary.status)}
      />
    </div>
  );
}

function ArticleFileNameCell({
  summary,
  onViewOriginal,
}: {
  summary: DocumentTaxonomySummary;
  onViewOriginal: (summary: DocumentTaxonomySummary) => void;
}) {
  const title = getDocumentTitle(summary);
  const canPreview = canPreviewArticleOriginal(summary);

  return (
    <div className="min-w-0 overflow-hidden" title={title}>
      <button
        type="button"
        className="block w-full min-w-0 overflow-hidden text-left outline-hidden disabled:cursor-default"
        onClick={() => canPreview && onViewOriginal(summary)}
        disabled={!canPreview}
      >
        <span className="block max-w-full truncate">
          <Text
            as="span"
            font="main-ui-action"
            color={canPreview ? "text-05" : "text-03"}
            nowrap
          >
            {title}
          </Text>
        </span>
      </button>
    </div>
  );
}

function ArticleTimeCell({ summary }: { summary: DocumentTaxonomySummary }) {
  const timestamp = formatDate(summary.generated_at || summary.updated_at);

  return (
    <div className="flex min-w-0 justify-center" title={timestamp}>
      <Text as="p" font="secondary-body" color="text-03" maxLines={1}>
        {timestamp}
      </Text>
    </div>
  );
}

function getDocumentTaxonomyTagTitle(tag: DocumentTaxonomyTag) {
  return `${tag.full_path_snapshot} · ${(tag.confidence * 100).toFixed(0)}%`;
}

function isTaskGeneratedTag(tag: DocumentTaxonomyTag) {
  return tag.source === "task_generated";
}

function NewTagBadge() {
  return (
    <div className="flex h-4 shrink-0 items-center rounded-04 bg-theme-green-01 px-1 text-theme-green-05">
      <Text as="p" font="figure-small-value" color="inherit" nowrap>
        新增
      </Text>
    </div>
  );
}

function ArticleTagPill({
  tag,
  maxWidthClassName = "max-w-full",
}: {
  tag: DocumentTaxonomyTag;
  maxWidthClassName?: string;
}) {
  const title = getDocumentTaxonomyTagTitle(tag);
  const isNew = isTaskGeneratedTag(tag);
  const colorClass =
    tag.review_status === "confirmed"
      ? "bg-theme-green-01 text-theme-green-05"
      : "bg-theme-blue-01 text-theme-blue-05";
  const tooltip = isNew ? `${title}\n自检 Agent 新增标签` : title;

  return (
    <Tooltip tooltip={tooltip}>
      <div
        className={`flex h-4 ${maxWidthClassName} min-w-0 items-center overflow-hidden rounded-04 px-1 ${colorClass}`}
        title={tooltip}
      >
        <Text as="p" font="figure-small-value" color="inherit" maxLines={1}>
          {title}
        </Text>
      </div>
    </Tooltip>
  );
}

function CompactArticleTag({ tag }: { tag: DocumentTaxonomyTag }) {
  const isNew = isTaskGeneratedTag(tag);

  return (
    <div className="flex min-w-0 items-center gap-1">
      <ArticleTagPill tag={tag} />
      {isNew && (
        <Tooltip tooltip="自检 Agent 新增的三级标签">
          <NewTagBadge />
        </Tooltip>
      )}
    </div>
  );
}

function CompactHiddenTagCount({
  count,
  tags,
}: {
  count: number;
  tags: DocumentTaxonomyTag[];
}) {
  const title = tags.map(getDocumentTaxonomyTagTitle).join("\n");

  return (
    <div
      className="flex h-4 shrink-0 items-center rounded-04 bg-background-tint-02 px-1"
      title={title}
    >
      <Text as="p" font="figure-small-value" color="text-03" nowrap>
        {`+${count}`}
      </Text>
    </div>
  );
}

function ArticleTagsCell({
  summary,
  tags,
  hasActiveTaggingTask,
}: {
  summary: DocumentTaxonomySummary;
  tags: DocumentTaxonomyTag[];
  hasActiveTaggingTask: boolean;
}) {
  if (articleTagsAreProcessing({ summary, hasActiveTaggingTask })) {
    return (
      <div className="flex min-w-0 justify-center">
        <ProcessingCellIndicator
          ariaLabel="标签等待处理"
          tooltip={
            summary.status === "pending"
              ? "等待 Summary 完成后自动打标签"
              : "正在生成标签"
          }
        />
      </div>
    );
  }

  const failedTag = tags.find((tag) => tag.status === "tagging_failed");
  if (failedTag) {
    const failedStatus = <Tag title="打标签失败" color="amber" />;
    return (
      <div className="flex min-w-0 justify-center">
        {failedTag.unmatched_reason ? (
          <Tooltip tooltip={failedTag.unmatched_reason}>{failedStatus}</Tooltip>
        ) : (
          failedStatus
        )}
      </div>
    );
  }

  const activeTags = tags.filter((tag) => tag.status === "active");
  const visibleTags = activeTags.slice(0, 1);
  const hiddenTags = activeTags.slice(visibleTags.length);
  const hiddenCount = hiddenTags.length;

  if (!activeTags.length) {
    return (
      <div className="flex min-w-0 justify-center">
        <Tag title="暂无标签" color="gray" />
      </div>
    );
  }

  return (
    <div className="flex min-w-0 items-center justify-center gap-1.5 overflow-hidden">
      {visibleTags.map((tag) => (
        <CompactArticleTag key={tag.id} tag={tag} />
      ))}
      {hiddenCount > 0 && (
        <CompactHiddenTagCount count={hiddenCount} tags={hiddenTags} />
      )}
    </div>
  );
}

function ArticleDetailCell({
  summary,
  onEditSummary,
  onDeleteSummary,
}: {
  summary: DocumentTaxonomySummary;
  onEditSummary: (summary: DocumentTaxonomySummary) => void;
  onDeleteSummary: (summary: DocumentTaxonomySummary) => void;
}) {
  return (
    <div className="flex min-w-0 justify-end gap-1">
      <Button
        aria-label="查看文章详情"
        icon={SvgEdit}
        prominence="tertiary"
        size="sm"
        tooltip="查看并编辑 Summary"
        onClick={() => onEditSummary(summary)}
      >
        详情
      </Button>
      <Button
        aria-label="删除文章"
        icon={SvgTrash}
        prominence="tertiary"
        variant="danger"
        size="sm"
        tooltip="删除文章"
        onClick={() => onDeleteSummary(summary)}
      />
    </div>
  );
}

function ArticleDeleteConfirmModal({
  summary,
  deleting,
  onClose,
  onConfirm,
}: {
  summary: DocumentTaxonomySummary | null;
  deleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  if (!summary) {
    return null;
  }

  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open && !deleting) {
          onClose();
        }
      }}
    >
      <Modal.Content width="sm" height="fit">
        <Modal.Header
          icon={SvgTrash}
          title="删除文章"
          description="删除后会从文章导入列表、标签结果和文档索引中移除。"
          onClose={deleting ? undefined : onClose}
        />
        <Modal.Body>
          <Text as="p" font="main-ui-body" color="text-04">
            {`确定删除「${getDocumentTitle(summary)}」吗？`}
          </Text>
        </Modal.Body>
        <Modal.Footer>
          <Button prominence="secondary" onClick={onClose} disabled={deleting}>
            取消
          </Button>
          <Button
            icon={deleting ? SpinningLoaderIcon : SvgTrash}
            prominence="primary"
            variant="danger"
            onClick={onConfirm}
            disabled={deleting}
          >
            {deleting ? "删除中" : "删除"}
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

function SummaryEditorModal({
  summary,
  initialShowOriginal = false,
  onClose,
}: {
  summary: DocumentTaxonomySummary | null;
  initialShowOriginal?: boolean;
  onClose: () => void;
}) {
  const tags = useDocumentTaxonomyTags(summary?.document_id ?? "");
  const [value, setValue] = useState(summary?.summary ?? "");
  const [lastSavedValue, setLastSavedValue] = useState(summary?.summary ?? "");
  const [saving, setSaving] = useState(false);
  const [showOriginal, setShowOriginal] = useState(initialShowOriginal);
  const activeTags = tags.filter((tag) => tag.status === "active");
  const taskGeneratedTags = activeTags.filter(isTaskGeneratedTag);
  const originalCanPreview = summary
    ? canPreviewArticleOriginal(summary)
    : false;

  useEffect(() => {
    const nextValue = summary?.summary ?? "";
    setValue(nextValue);
    setLastSavedValue(nextValue);
    setShowOriginal(initialShowOriginal);
  }, [initialShowOriginal, summary?.document_id, summary?.summary]);

  const handleClose = () => {
    if (saving) {
      return;
    }
    onClose();
  };

  const handleSave = async () => {
    if (!summary) {
      return;
    }

    setSaving(true);
    try {
      await updateSummary(summary.document_id, value);
      setLastSavedValue(value);
      toast.success("Summary 已保存，正在自动重新打标签");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Summary 保存失败");
    } finally {
      setSaving(false);
    }
  };
  const summaryHasChanges = summary != null && value !== lastSavedValue;
  const modalTitle = showOriginal ? "查看原文" : "编辑 Summary";

  return (
    <Modal open={!!summary} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <Modal.Content
        width={showOriginal ? "full" : "lg"}
        height="lg"
        background="gray"
      >
        <Modal.Header
          icon={showOriginal ? SvgBookOpen : SvgFileText}
          title={modalTitle}
          description={
            summary
              ? `${getDocumentTitle(summary)} · 保存后会自动重新打标签`
              : "保存后会自动重新打标签"
          }
          onClose={handleClose}
        />
        <Modal.Body>
          {summary && (
            <div
              className={
                showOriginal
                  ? "grid w-full grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] items-start gap-4"
                  : "w-full"
              }
            >
              <Section gap={1} alignItems="stretch">
                <Card border="solid" rounding="md" padding="md">
                  <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4">
                    <div className="min-w-0">
                      <button
                        type="button"
                        className="block max-w-full text-left outline-hidden"
                        onClick={() =>
                          originalCanPreview && setShowOriginal(true)
                        }
                        disabled={!originalCanPreview}
                      >
                        <Text
                          as="span"
                          font="main-ui-action"
                          color={originalCanPreview ? "text-05" : "text-03"}
                          maxLines={2}
                        >
                          {getDocumentTitle(summary)}
                        </Text>
                      </button>
                      <Text
                        as="p"
                        font="secondary-body"
                        color="text-03"
                        maxLines={1}
                      >
                        {formatDate(summary.generated_at || summary.updated_at)}
                      </Text>
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-1.5">
                      <Tag
                        title={getSummaryStatusLabel(summary.status)}
                        color={getSummaryStatusColor(summary.status)}
                      />
                      <Tag
                        title={summary.is_manual ? "人工摘要" : "AI 摘要"}
                        color={summary.is_manual ? "purple" : "gray"}
                      />
                      <Tag
                        title={getArticleLabelStatusTag(summary).title}
                        color={getArticleLabelStatusTag(summary).color}
                      />
                    </div>
                  </div>
                </Card>

                <InputVertical title="Summary" withLabel>
                  <InputTextArea
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    rows={showOriginal ? 6 : 8}
                    maxRows={showOriginal ? 8 : 16}
                    autoResize
                    placeholder="文章入库后会自动生成 Summary，可在这里手动修改。"
                  />
                </InputVertical>

                <Card
                  border="solid"
                  rounding="md"
                  padding="md"
                  background="light"
                >
                  <div className="flex min-w-0 flex-col gap-3">
                    <div className="flex items-center justify-between gap-3">
                      <Text font="main-ui-action" color="text-05">
                        标签结果
                      </Text>
                      <Text font="secondary-body" color="text-03">
                        {`${activeTags.length} 个有效标签`}
                      </Text>
                    </div>
                    <ArticleTagResultList tags={tags} />
                    {taskGeneratedTags.length > 0 && (
                      <div className="flex min-w-0 flex-col gap-2 rounded-04 border border-theme-green-02 bg-theme-green-01 px-3 py-2">
                        <div className="flex items-center gap-1.5">
                          <NewTagBadge />
                          <div className="text-theme-green-05">
                            <Text font="main-ui-action" color="inherit">
                              本次新增标签
                            </Text>
                          </div>
                        </div>
                        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                          {taskGeneratedTags.map((tag) => (
                            <ArticleTagPill
                              key={tag.id}
                              tag={tag}
                              maxWidthClassName="max-w-[20rem]"
                            />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </Card>
              </Section>
              {showOriginal && (
                <ArticleOriginalViewer
                  summary={summary}
                  onClose={() => setShowOriginal(false)}
                />
              )}
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          {summary && (
            <Button
              icon={showOriginal ? SvgFileText : SvgBookOpen}
              prominence="tertiary"
              onClick={() => setShowOriginal((current) => !current)}
              disabled={!originalCanPreview}
            >
              {showOriginal ? "隐藏原文" : "查看原文"}
            </Button>
          )}
          <Button prominence="secondary" onClick={handleClose}>
            关闭
          </Button>
          <Button
            icon={saving ? SpinningLoaderIcon : SvgCheck}
            prominence="primary"
            onClick={handleSave}
            disabled={!summaryHasChanges || saving}
          >
            {saving ? "保存中" : "保存 Summary"}
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

function ArticleMarkdownPreview({ content }: { content: string }) {
  return (
    <ReactMarkdown
      className="prose max-w-none text-text-04"
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }) => (
          <div className="overflow-auto rounded-08 border border-border-01">
            <table className="min-w-full border-collapse">{children}</table>
          </div>
        ),
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-link underline"
          >
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function ArticleOriginalViewer({
  summary,
  onClose,
}: {
  summary: DocumentTaxonomySummary;
  onClose: () => void;
}) {
  const originalKind = getArticleOriginalKind(summary);
  const originalUrl = getImportedArticleOriginalUrl(summary.document_id);
  const [markdownContent, setMarkdownContent] = useState<string | null>(null);
  const [loadingMarkdown, setLoadingMarkdown] = useState(false);
  const [markdownError, setMarkdownError] = useState<string | null>(null);

  useEffect(() => {
    if (originalKind !== "markdown") {
      setMarkdownContent(null);
      setMarkdownError(null);
      setLoadingMarkdown(false);
      return;
    }

    let ignore = false;
    setLoadingMarkdown(true);
    setMarkdownError(null);
    fetchImportedArticleOriginal(summary.document_id)
      .then((content) => {
        if (!ignore) {
          setMarkdownContent(content);
        }
      })
      .catch((error) => {
        if (!ignore) {
          setMarkdownError(
            error instanceof Error ? error.message : "原文加载失败"
          );
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoadingMarkdown(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [originalKind, summary.document_id]);

  let body: ReactNode;
  if (originalKind === "pdf") {
    body = (
      <iframe
        title={`原文：${getDocumentTitle(summary)}`}
        src={originalUrl}
        className="h-[34rem] w-full rounded-08 border border-border-01 bg-background-tint-00"
      />
    );
  } else if (originalKind === "markdown") {
    if (loadingMarkdown) {
      body = (
        <div className="flex h-[34rem] items-center justify-center rounded-08 border border-border-01 bg-background-tint-00">
          <div className="flex items-center gap-2 text-text-03">
            <SvgLoader size={16} className="animate-spin" />
            <Text font="secondary-body" color="inherit">
              原文加载中
            </Text>
          </div>
        </div>
      );
    } else if (markdownError) {
      body = (
        <MessageCard
          variant="warning"
          title="原文加载失败"
          description={markdownError}
          padding="sm"
        />
      );
    } else {
      body = (
        <div className="h-[34rem] overflow-auto rounded-08 border border-border-01 bg-background-tint-00 p-4">
          <pre className="m-0 whitespace-pre-wrap break-words font-mono text-sm leading-6 text-text-04">
            {markdownContent ?? ""}
          </pre>
        </div>
      );
    }
  } else {
    body = (
      <MessageCard
        variant="warning"
        title="暂不支持预览"
        description="当前仅支持 Markdown 和 PDF 原文预览。"
        padding="sm"
      />
    );
  }

  return (
    <Card border="solid" rounding="md" padding="fit" background="light">
      <div className="flex min-h-0 flex-col">
        <div className="flex items-start justify-between gap-3 border-b border-border-01 px-4 py-3">
          <div className="flex min-w-0 items-start gap-2">
            <div className="shrink-0 pt-0.5 text-text-04">
              {originalKind === "pdf" ? (
                <SvgFileText size={16} />
              ) : (
                <SvgBookOpen size={16} />
              )}
            </div>
            <div className="min-w-0">
              <Text as="p" font="main-ui-action" color="text-05" nowrap>
                原文内容
              </Text>
              <Text as="p" font="secondary-body" color="text-03" maxLines={1}>
                {getDocumentTitle(summary)}
              </Text>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button
              href={originalUrl}
              target="_blank"
              icon={SvgExternalLink}
              prominence="tertiary"
              size="sm"
              tooltip="新标签页打开"
            />
            <Button
              aria-label="隐藏原文"
              icon={SvgX}
              prominence="tertiary"
              size="sm"
              tooltip="隐藏原文"
              onClick={onClose}
            />
          </div>
        </div>
        <div className="p-3">{body}</div>
      </div>
    </Card>
  );
}

function ImportedArticleRow({
  articleNumber,
  summary,
  hasActiveTaggingTask,
  onEditSummary,
  onViewOriginal,
  onDeleteSummary,
}: {
  articleNumber: number;
  summary: DocumentTaxonomySummary;
  hasActiveTaggingTask: boolean;
  onEditSummary: (summary: DocumentTaxonomySummary) => void;
  onViewOriginal: (summary: DocumentTaxonomySummary) => void;
  onDeleteSummary: (summary: DocumentTaxonomySummary) => void;
}) {
  const tags = useDocumentTaxonomyTags(summary.document_id);

  return (
    <div className="border-b border-border-01 px-4 py-2.5 last:border-b-0">
      <div
        className="grid w-full items-center gap-3"
        style={{ gridTemplateColumns: IMPORTED_ARTICLES_GRID_COLUMNS }}
      >
        <div className="flex min-w-0 justify-start">
          <Text as="p" font="main-ui-action" color="text-03" nowrap>
            {String(articleNumber)}
          </Text>
        </div>
        <ArticleFileNameCell
          summary={summary}
          onViewOriginal={onViewOriginal}
        />
        <ArticleTimeCell summary={summary} />
        <ArticleSummaryStatus summary={summary} />
        <ArticleProgressCell
          summary={summary}
          hasActiveTaggingTask={hasActiveTaggingTask}
        />
        <ArticleTagsCell
          summary={summary}
          tags={tags}
          hasActiveTaggingTask={hasActiveTaggingTask}
        />
        <ArticleDetailCell
          summary={summary}
          onEditSummary={onEditSummary}
          onDeleteSummary={onDeleteSummary}
        />
      </div>
    </div>
  );
}

function ArticleMetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <Card border="solid" rounding="lg" padding="lg">
      <div className="flex min-w-0 flex-col gap-2">
        <Text as="p" font="figure-small-label" color="text-03" nowrap>
          {label}
        </Text>
        <Text as="p" font="heading-h3" color="text-05" maxLines={1}>
          {value}
        </Text>
        {detail && (
          <Text as="p" font="secondary-body" color="text-03" maxLines={2}>
            {detail}
          </Text>
        )}
      </div>
    </Card>
  );
}

function ArticleListHeader({ count }: { count: number }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <div className="min-w-0">
        <Text as="h2" font="heading-h3" color="text-05">
          文章列表 / 详情区
        </Text>
        <Text as="p" font="secondary-body" color="text-03">
          查看每篇文章的处理进度、摘要状态与标签结果。
        </Text>
      </div>
      <Text font="secondary-body" color="text-03">
        {`${count} 篇文章`}
      </Text>
    </div>
  );
}

function ImportedArticlesList({
  summaries,
  hasActiveTaggingTask,
}: {
  summaries: DocumentTaxonomySummary[];
  hasActiveTaggingTask: boolean;
}) {
  const [editingSummary, setEditingSummary] =
    useState<DocumentTaxonomySummary | null>(null);
  const [
    editingSummaryStartsWithOriginal,
    setEditingSummaryStartsWithOriginal,
  ] = useState(false);
  const [deletingSummary, setDeletingSummary] =
    useState<DocumentTaxonomySummary | null>(null);
  const [deletingArticle, setDeletingArticle] = useState(false);

  const handleDeleteArticle = async () => {
    if (!deletingSummary) {
      return;
    }

    setDeletingArticle(true);
    try {
      await deleteImportedArticle(deletingSummary.document_id);
      toast.success("文章已删除");
      setDeletingSummary(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "文章删除失败");
    } finally {
      setDeletingArticle(false);
    }
  };

  const handleEditSummary = (summary: DocumentTaxonomySummary) => {
    setEditingSummaryStartsWithOriginal(false);
    setEditingSummary(summary);
  };

  const handleViewOriginal = (summary: DocumentTaxonomySummary) => {
    setEditingSummaryStartsWithOriginal(true);
    setEditingSummary(summary);
  };

  return (
    <>
      <Card border="solid" rounding="lg" padding="fit">
        <div className="flex min-w-0 flex-col">
          <div className="border-b border-border-01 px-4 py-4">
            <ArticleListHeader count={summaries.length} />
          </div>
          <div className="border-b border-border-01 bg-background-tint-01 px-4 py-2.5">
            <div
              className="grid w-full items-center gap-3"
              style={{ gridTemplateColumns: IMPORTED_ARTICLES_GRID_COLUMNS }}
            >
              <div className="flex justify-start">
                <Text font="figure-small-label" color="text-03">
                  序号
                </Text>
              </div>
              <Text font="figure-small-label" color="text-03">
                文件名
              </Text>
              <div className="flex justify-center">
                <Text font="figure-small-label" color="text-03">
                  生成/更新时间
                </Text>
              </div>
              <div className="flex justify-center">
                <Text font="figure-small-label" color="text-03">
                  Summary
                </Text>
              </div>
              <div className="flex justify-center">
                <Text font="figure-small-label" color="text-03">
                  进度
                </Text>
              </div>
              <div className="flex justify-center">
                <Text font="figure-small-label" color="text-03">
                  标签
                </Text>
              </div>
              <div className="flex justify-end">
                <Text font="figure-small-label" color="text-03">
                  详情
                </Text>
              </div>
            </div>
          </div>
          {summaries.map((summary, index) => (
            <ImportedArticleRow
              key={summary.document_id}
              articleNumber={index + 1}
              summary={summary}
              hasActiveTaggingTask={hasActiveTaggingTask}
              onEditSummary={handleEditSummary}
              onViewOriginal={handleViewOriginal}
              onDeleteSummary={setDeletingSummary}
            />
          ))}
        </div>
      </Card>
      <SummaryEditorModal
        summary={editingSummary}
        initialShowOriginal={editingSummaryStartsWithOriginal}
        onClose={() => {
          setEditingSummary(null);
          setEditingSummaryStartsWithOriginal(false);
        }}
      />
      <ArticleDeleteConfirmModal
        summary={deletingSummary}
        deleting={deletingArticle}
        onClose={() => !deletingArticle && setDeletingSummary(null)}
        onConfirm={handleDeleteArticle}
      />
    </>
  );
}

function ImportArticlesModal({
  open,
  onClose,
  onImportQueued,
}: {
  open: boolean;
  onClose: () => void;
  onImportQueued: () => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleClose = () => {
    if (submitting) {
      return;
    }
    reset();
    onClose();
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setFiles(Array.from(event.target.files ?? []));
  };

  const handleSubmit = async () => {
    if (!files.length) {
      toast.error("请选择要导入的 Markdown 或 PDF 文件");
      return;
    }

    setSubmitting(true);
    try {
      const result = await importArticles(files);
      if (result.imported.length) {
        toast.success(`已上传 ${result.imported.length} 个文件`, {
          description: "后台会继续完成解析、Summary 和打标签。",
        });
      }
      if (result.failed.length) {
        toast.error(`${result.failed.length} 个文件导入失败`, {
          description: result.failed
            .map((item) => `${item.file_name}: ${item.detail ?? "导入失败"}`)
            .join("\n"),
        });
      }
      if (result.imported.length) {
        reset();
        onImportQueued();
        onClose();
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "文章导入失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <Modal.Content width="md" height="fit">
        <Modal.Header
          icon={SvgUploadCloud}
          title="导入文章"
          description="上传 Markdown 或 PDF 文件，系统会复用现有文档入库、解析、Summary 和打标签链路。"
          onClose={handleClose}
        />
        <Modal.Body>
          <Section gap={0.75} alignItems="stretch">
            <input
              ref={fileInputRef}
              type="file"
              accept=".md,.markdown,.pdf,text/markdown,text/x-markdown,application/pdf"
              multiple
              onChange={handleFileChange}
              className="hidden"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                icon={SvgUploadCloud}
                prominence="secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={submitting}
              >
                选择文件
              </Button>
              <Text as="span" font="secondary-body" color="text-03">
                {files.length ? `${files.length} 个文件已选择` : "未选择文件"}
              </Text>
            </div>
            {files.length > 0 && (
              <Section gap={0.25} alignItems="stretch">
                {files.map((file) => (
                  <Text
                    key={`${file.name}-${file.size}-${file.lastModified}`}
                    as="p"
                    font="secondary-body"
                    color="text-03"
                    maxLines={1}
                  >
                    {file.name}
                  </Text>
                ))}
              </Section>
            )}
          </Section>
        </Modal.Body>
        <Modal.Footer>
          <Button prominence="secondary" onClick={handleClose}>
            取消
          </Button>
          <Button
            icon={submitting ? SpinningLoaderIcon : SvgUploadCloud}
            prominence="primary"
            onClick={handleSubmit}
            disabled={submitting || !files.length}
          >
            {submitting ? "上传中" : "上传并处理"}
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

function ImportedArticlesPanel({
  dashboard,
  queuedImportActive,
}: {
  dashboard?: TaxonomyDashboard;
  queuedImportActive: boolean;
}) {
  const latestTask = getLatestImportTask(dashboard?.recent_tasks);
  const summaries = dashboard?.summaries ?? [];
  const hasActiveTaxonomy = Boolean(dashboard?.taxonomy?.active_version_id);
  const activeTask = taxonomyTaskIsActive(latestTask) ? latestTask : undefined;
  const totalDocuments = dashboard?.coverage.total_documents ?? 0;
  const labeledDocuments = dashboard?.coverage.labeled_documents ?? 0;
  const coveragePercent =
    dashboard?.coverage.coverage_percent?.toFixed(1) ?? "0.0";
  let importStatusTitle = "空闲";
  if (queuedImportActive) {
    importStatusTitle = "后台接收中";
  }
  if (activeTask) {
    importStatusTitle = `${getTaskStatusLabel(activeTask.status)} ${activeTask.processed_docs}/${activeTask.total_docs}`;
  }

  return (
    <Section id="imported-articles" gap={2} alignItems="stretch">
      <div className="grid w-full grid-cols-4 gap-4">
        <ArticleMetricCard
          label="入库文章"
          value={`${totalDocuments} 篇`}
          detail="当前可处理文章"
        />
        <ArticleMetricCard
          label="已打标签"
          value={`${labeledDocuments} 篇`}
          detail="含有效标签结果"
        />
        <ArticleMetricCard
          label="覆盖率"
          value={`${coveragePercent}%`}
          detail="已打标签 / 入库文章"
        />
        <ArticleMetricCard
          label="处理状态"
          value={importStatusTitle}
          detail={hasActiveTaxonomy ? "可继续导入文章" : "需启用标签体系"}
        />
      </div>

      {summaries.length ? (
        <ImportedArticlesList
          summaries={summaries}
          hasActiveTaggingTask={queuedImportActive || Boolean(activeTask)}
        />
      ) : (
        <ImportedArticlesEmptyState queued={queuedImportActive} />
      )}
    </Section>
  );
}

function ImportedArticlesEmptyState({ queued = false }: { queued?: boolean }) {
  const description = queued
    ? "上传完成后会在这里显示处理进度"
    : "导入 Markdown 或 PDF 后会在这里查看 Summary 和标签";

  return (
    <Card border="dashed" rounding="md" padding="lg" background="light">
      <div className="flex justify-center">
        <div className="flex max-w-md flex-col items-center gap-2 text-center">
          <Content
            icon={SvgFileText}
            title={queued ? "后台正在接收文章" : "暂无导入文章"}
            sizePreset="secondary"
            variant="body"
            color="muted"
            width="fit"
          />
          <Text as="p" font="secondary-body" color="text-03" maxLines={2}>
            {description}
          </Text>
        </div>
      </div>
    </Card>
  );
}

function SummaryEditor({
  summary,
  compact = false,
}: {
  summary: DocumentTaxonomySummary;
  compact?: boolean;
}) {
  const [value, setValue] = useState(summary.summary ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValue(summary.summary ?? "");
  }, [summary.document_id, summary.summary]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSummary(summary.document_id, value);
      toast.success("Summary 已保存，正在自动重新打标签");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Summary 保存失败");
    } finally {
      setSaving(false);
    }
  };

  const editor = (
    <Section gap={0.5}>
      {!compact && (
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <Text font="main-ui-action" color="text-05" maxLines={1}>
              {summary.semantic_id || summary.document_id}
            </Text>
            <Text as="p" font="secondary-body" color="text-03" maxLines={1}>
              {`${getSummaryStatusLabel(summary.status)} · ${summary.is_manual ? "人工摘要" : "AI 摘要"} · ${formatDate(summary.generated_at || summary.updated_at)}`}
            </Text>
          </div>
          <Tag
            title={getArticleLabelStatusTag(summary).title}
            color={getArticleLabelStatusTag(summary).color}
          />
        </div>
      )}
      <InputTextArea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={compact ? 2 : 3}
        maxRows={10}
        autoResize
        placeholder="文章入库后会自动生成 Summary，可在这里手动修改。"
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Text as="p" font="secondary-body" color="text-03">
          保存后会自动重新打标签
        </Text>
        <Button
          prominence="tertiary"
          size="sm"
          icon={saving ? SpinningLoaderIcon : SvgCheck}
          onClick={handleSave}
          disabled={saving || value === (summary.summary ?? "")}
        >
          {saving ? "保存中" : "保存 Summary"}
        </Button>
      </div>
    </Section>
  );

  return compact ? (
    editor
  ) : (
    <Card border="solid" rounding="md">
      {editor}
    </Card>
  );
}

function SummariesPanel({ dashboard }: { dashboard?: TaxonomyDashboard }) {
  const [summaryDocumentIds, setSummaryDocumentIds] = useState("");
  const [summaryLimit, setSummaryLimit] = useState("20");
  const [overwriteManual, setOverwriteManual] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const handleGenerateSummaries = async () => {
    setBusyAction("summaries");
    try {
      const result = await generateSummaries({
        document_ids: parseDocumentIds(summaryDocumentIds),
        limit: Number(summaryLimit) || 20,
        overwrite_manual: overwriteManual,
      });
      toast.success(`${result.processed} summaries processed`);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Summary task failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <Card border="solid" rounding="lg">
      <CardLayout.Header>
        <div className="p-2">
          <Content
            icon={SvgRefreshCw}
            title="Summaries"
            description="Generate or edit document summaries used by taxonomy tagging."
            sizePreset="main-ui"
            variant="section"
          />
        </div>
      </CardLayout.Header>
      <Divider paddingParallel="fit" paddingPerpendicular="fit" />
      <Section gap={0.75} alignItems="stretch" justifyContent="start">
        <FormGrid>
          <FullWidthField>
            <InputVertical title="Document IDs" withLabel>
              <InputTextArea
                value={summaryDocumentIds}
                onChange={(e) => setSummaryDocumentIds(e.target.value)}
                rows={2}
                maxRows={5}
                autoResize
                placeholder="Optional comma or newline separated document IDs"
              />
            </InputVertical>
          </FullWidthField>
          <InputVertical title="Limit" withLabel>
            <InputTypeIn
              value={summaryLimit}
              onChange={(e) => setSummaryLimit(e.target.value)}
              inputMode="numeric"
              showClearButton={false}
            />
          </InputVertical>
          <InputVertical title="Overwrite Manual" withLabel>
            <Switch
              checked={overwriteManual}
              onCheckedChange={setOverwriteManual}
            />
          </InputVertical>
        </FormGrid>
        <div className="flex justify-end">
          <Button
            prominence="primary"
            icon={SvgRefreshCw}
            onClick={handleGenerateSummaries}
            disabled={busyAction === "summaries"}
          >
            Generate Summaries
          </Button>
        </div>
        {dashboard?.summaries?.length ? (
          <Section gap={0.5}>
            {dashboard.summaries.map((summary) => (
              <SummaryEditor key={summary.document_id} summary={summary} />
            ))}
          </Section>
        ) : (
          <EmptyMessageCard sizePreset="main-ui" title="No summaries yet" />
        )}
      </Section>
    </Card>
  );
}

function BatchTaggingPanel({ dashboard }: { dashboard?: TaxonomyDashboard }) {
  const [taggingDocumentIds, setTaggingDocumentIds] = useState("");
  const [taggingLimit, setTaggingLimit] = useState("50");
  const [taggingSource, setTaggingSource] =
    useState<TaxonomyTaggingSource>("summary");
  const [enableOptimization, setEnableOptimization] = useState(false);
  const [optimizationStrength, setOptimizationStrength] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const handleRunTagging = async () => {
    if (!dashboard?.taxonomy?.active_version_id) {
      toast.error("Activate a taxonomy version first");
      return;
    }
    setBusyAction("tagging");
    try {
      const task = await runTagging({
        document_ids: parseDocumentIds(taggingDocumentIds),
        source: taggingSource,
        enable_optimization: enableOptimization,
        optimization_strength: optimizationStrength || null,
        limit: Number(taggingLimit) || 50,
      });
      toast.success(
        `Tagging task ${task.id}: ${task.processed_docs}/${task.total_docs} processed`
      );
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Tagging task failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <Card border="solid" rounding="lg">
      <CardLayout.Header>
        <div className="p-2">
          <Content
            icon={SvgTag}
            title="Batch Tagging"
            description="Apply the active taxonomy version to documents and project leaf labels to searchable metadata."
            sizePreset="main-ui"
            variant="section"
          />
        </div>
      </CardLayout.Header>
      <Divider paddingParallel="fit" paddingPerpendicular="fit" />
      <Section gap={0.75} alignItems="stretch" justifyContent="start">
        <FormGrid>
          <FullWidthField>
            <InputVertical title="Document IDs" withLabel>
              <InputTextArea
                value={taggingDocumentIds}
                onChange={(e) => setTaggingDocumentIds(e.target.value)}
                rows={2}
                maxRows={5}
                autoResize
                placeholder="Optional comma or newline separated document IDs"
              />
            </InputVertical>
          </FullWidthField>
          <InputVertical title="Source" withLabel>
            <InputSelect
              value={taggingSource}
              onValueChange={(value) =>
                setTaggingSource(value as TaxonomyTaggingSource)
              }
            >
              <InputSelect.Trigger />
              <InputSelect.Content>
                <InputSelect.Item value="summary">Summary</InputSelect.Item>
                <InputSelect.Item value="original">
                  Original content
                </InputSelect.Item>
              </InputSelect.Content>
            </InputSelect>
          </InputVertical>
          <InputVertical title="Limit" withLabel>
            <InputTypeIn
              value={taggingLimit}
              onChange={(e) => setTaggingLimit(e.target.value)}
              inputMode="numeric"
              showClearButton={false}
            />
          </InputVertical>
          <InputVertical title="Taxonomy Optimization" withLabel>
            <Switch
              checked={enableOptimization}
              onCheckedChange={setEnableOptimization}
            />
          </InputVertical>
          <InputVertical title="Optimization Strength" withLabel>
            <InputTypeIn
              value={optimizationStrength}
              onChange={(e) => setOptimizationStrength(e.target.value)}
              placeholder="conservative, balanced..."
            />
          </InputVertical>
        </FormGrid>
        {enableOptimization && (
          <MessageCard
            title="Optimization can create candidate leaf labels"
            description="New labels remain candidates for governance and versioning review."
            padding="xs"
          />
        )}
        <div className="flex justify-end">
          <Button
            prominence="primary"
            icon={SvgTag}
            onClick={handleRunTagging}
            disabled={busyAction === "tagging"}
          >
            Run Tagging
          </Button>
        </div>
        {dashboard?.recent_tasks?.length ? (
          <Section gap={0.5}>
            {dashboard.recent_tasks.map((task) => (
              <Card key={task.id} border="solid" rounding="md">
                <InputHorizontal
                  title={`Task ${task.id}`}
                  description={`${task.status} · ${task.processed_docs}/${task.total_docs} processed · ${formatDate(task.created_at)}`}
                  withLabel
                >
                  <Tag
                    title={
                      task.failed_docs
                        ? `${task.failed_docs} failed`
                        : task.source
                    }
                    color={task.failed_docs ? "amber" : "green"}
                  />
                </InputHorizontal>
              </Card>
            ))}
          </Section>
        ) : (
          <EmptyMessageCard sizePreset="main-ui" title="No tagging tasks yet" />
        )}
      </Section>
    </Card>
  );
}

function QueryMatchPanel() {
  const [query, setQuery] = useState("");
  const [applyTo, setApplyTo] = useState<TaxonomySearchApplyTo>("search");
  const [decision, setDecision] = useState<TaxonomySearchDecision | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const handleMatchQuery = async () => {
    if (!query.trim()) {
      toast.error("Enter a query first");
      return;
    }
    setBusyAction("match");
    try {
      const nextDecision = await matchTaxonomyQuery({
        query,
        apply_to: applyTo,
      });
      setDecision(nextDecision);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Query match failed"
      );
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <Card border="solid" rounding="lg">
      <CardLayout.Header>
        <div className="p-2">
          <Content
            icon={SvgSearch}
            title="Query Match"
            description="Test lightweight query-to-taxonomy matching before enabling filters in Chat Preferences."
            sizePreset="main-ui"
            variant="section"
          />
        </div>
      </CardLayout.Header>
      <Divider paddingParallel="fit" paddingPerpendicular="fit" />
      <Section gap={0.75} alignItems="stretch" justifyContent="start">
        <div className="grid gap-3 md:grid-cols-[1fr_180px]">
          <InputTypeIn
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search query to test"
            leftSearchIcon
          />
          <InputSelect
            value={applyTo}
            onValueChange={(value) =>
              setApplyTo(value as TaxonomySearchApplyTo)
            }
          >
            <InputSelect.Trigger />
            <InputSelect.Content>
              <InputSelect.Item value="search">Search</InputSelect.Item>
              <InputSelect.Item value="chat">Chat</InputSelect.Item>
              <InputSelect.Item value="both">Both</InputSelect.Item>
            </InputSelect.Content>
          </InputSelect>
        </div>
        <div className="flex justify-end">
          <Button
            prominence="primary"
            icon={SvgSearch}
            onClick={handleMatchQuery}
            disabled={busyAction === "match"}
          >
            Match Query
          </Button>
        </div>
        {decision && (
          <Card border="solid" rounding="md">
            <Section gap={0.5}>
              <div className="flex flex-wrap items-center gap-2">
                <Tag
                  title={decision.recommended_action}
                  color={
                    decision.recommended_action === "hard_filter"
                      ? "amber"
                      : decision.matched
                        ? "green"
                        : "gray"
                  }
                />
                <Text font="main-ui-action" color="text-05">
                  {decision.path.join(" / ") || "No matched node"}
                </Text>
              </div>
              <Text as="p" font="secondary-body" color="text-03">
                {`Confidence ${(decision.confidence * 100).toFixed(1)}% · ${decision.elapsed_ms} ms · ${decision.reason}`}
              </Text>
              <Text as="p" font="secondary-body" color="text-03">
                {`Expanded leaves: ${decision.expanded_leaf_ids.length}`}
              </Text>
              {decision.candidates.length > 0 && (
                <Section gap={0.25}>
                  {decision.candidates.slice(0, 5).map((candidate) => (
                    <Text
                      key={candidate.node_id}
                      as="p"
                      font="secondary-body"
                      color="text-03"
                      maxLines={1}
                    >
                      {`${candidate.path.join(" / ")} · ${(candidate.confidence * 100).toFixed(1)}% · ${candidate.basis}`}
                    </Text>
                  ))}
                </Section>
              )}
            </Section>
          </Card>
        )}
      </Section>
    </Card>
  );
}

function ActiveTaxonomyPanel({
  dashboard,
  versions,
}: {
  dashboard?: TaxonomyDashboard;
  versions: TaxonomyVersion[];
}) {
  const activeVersion = dashboard?.taxonomy?.active_version;
  const activeCounts = activeVersion ? countNodes(activeVersion.nodes) : null;
  const draftCount = versions.filter(
    (version) => version.status === "draft"
  ).length;
  const historyDescription = versions.length
    ? `${versions.length} 个版本 · ${draftCount} 个草稿待生效`
    : "暂无版本记录";
  const activeVersionSummary = activeVersion
    ? `v${activeVersion.version_number} · ${activeCounts?.l1 ?? 0} 个一级 · ${activeCounts?.l2 ?? 0} 个二级 · ${activeCounts?.leaf ?? 0} 个三级`
    : "创建并生效草稿后，将在这里展示标签树";
  const healthSummary = activeVersion?.health_summary;
  const duplicateNamesRaw = healthSummary?.["duplicate_names"];
  const missingExampleNodesRaw = healthSummary?.["leaf_nodes_missing_examples"];
  const duplicateNames = Array.isArray(duplicateNamesRaw)
    ? duplicateNamesRaw.filter(
        (item): item is string => typeof item === "string" && item.length > 0
      )
    : [];
  const missingExampleNodes = Array.isArray(missingExampleNodesRaw)
    ? missingExampleNodesRaw.filter(
        (item): item is string => typeof item === "string" && item.length > 0
      )
    : [];
  const healthIssueCount = duplicateNames.length + missingExampleNodes.length;
  const healthIssueDescription = [
    duplicateNames.length ? `${duplicateNames.length} 个重复名称` : null,
    missingExampleNodes.length
      ? `${missingExampleNodes.length} 个三级标签缺少示例`
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <Section
      id="active-taxonomy"
      className="scroll-mt-24"
      alignItems="stretch"
      justifyContent="start"
      height="auto"
      gap={1}
    >
      <div className="grid grid-cols-3 gap-3">
        <StatCard
          title="覆盖率"
          value={`${dashboard?.coverage.coverage_percent?.toFixed(1) ?? "0.0"}%`}
          detail={`${dashboard?.coverage.labeled_documents ?? 0}/${dashboard?.coverage.total_documents ?? 0} 篇文章已打标`}
        />
        <StatCard
          title="当前版本"
          value={activeVersion ? `v${activeVersion.version_number}` : "无"}
          detail={
            activeVersion
              ? `${activeCounts?.leaf ?? 0} 个三级标签 · ${formatDate(activeVersion.effective_at)}`
              : "创建并启用草稿后开始打标"
          }
        />
        <StatCard
          title="版本总数"
          value={String(versions.length)}
          detail={`${draftCount} 个草稿待生效`}
        />
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_21rem] items-start gap-4">
        <Card border="solid" rounding="lg">
          <CardLayout.Header>
            <div className="p-2">
              <Content
                icon={SvgBlocks}
                title="当前生效版本"
                description={activeVersionSummary}
                sizePreset="main-ui"
                variant="section"
              />
            </div>
          </CardLayout.Header>
          <Divider paddingParallel="fit" paddingPerpendicular="fit" />
          {activeVersion ? (
            <Section alignItems="stretch" height="auto" gap={0.75}>
              {healthIssueCount > 0 && (
                <MessageCard
                  variant="warning"
                  title="标签体系需要检查"
                  description={healthIssueDescription}
                  padding="xs"
                />
              )}
              <TaxonomyTree nodes={activeVersion.nodes} />
            </Section>
          ) : (
            <EmptyMessageCard sizePreset="main-ui" title="暂无生效版本" />
          )}
        </Card>

        <Card border="solid" rounding="lg">
          <CardLayout.Header>
            <div className="p-2">
              <Content
                icon={SvgClock}
                title="版本记录"
                description={historyDescription}
                sizePreset="main-ui"
                variant="section"
              />
            </div>
          </CardLayout.Header>
          <Divider paddingParallel="fit" paddingPerpendicular="fit" />
          <Section alignItems="stretch" height="auto" gap={0.5}>
            {versions.length ? (
              versions.map((version) => (
                <Card key={version.id} border="solid" rounding="md">
                  <Section gap={0.5}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <Text font="main-ui-action" color="text-05">
                          {`v${version.version_number}`}
                        </Text>
                        <Text
                          as="p"
                          font="secondary-body"
                          color="text-03"
                          maxLines={2}
                        >
                          {getVersionHistoryDescription(version)}
                        </Text>
                      </div>
                      <Tag
                        title={getVersionStatusLabel(version.status)}
                        color={
                          version.status === "active"
                            ? "green"
                            : version.status === "draft"
                              ? "amber"
                              : "gray"
                        }
                      />
                    </div>
                    <Text font="secondary-body" color="text-03">
                      {getVersionSourceLabel(version.source)}
                    </Text>
                  </Section>
                </Card>
              ))
            ) : (
              <EmptyMessageCard sizePreset="main-ui" title="暂无版本记录" />
            )}
          </Section>
        </Card>
      </div>
    </Section>
  );
}

function GenerationNumberField({
  label,
  description,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  description: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="border-b border-border-02 py-3 last:border-b-0">
      <InputHorizontal title={label} description={description} withLabel>
        <InputTypeIn
          type="number"
          min={min}
          max={max}
          value={String(value)}
          onChange={(event) => {
            const parsedValue = Number(event.target.value);
            if (!Number.isNaN(parsedValue)) {
              onChange(parsedValue);
            }
          }}
          className="w-24"
        />
      </InputHorizontal>
    </div>
  );
}

function GenerationConfigStat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0">
      <Text as="p" font="heading-h3" color="text-05">
        {value}
      </Text>
      <Text as="p" font="figure-small-label" color="text-03" maxLines={1}>
        {label}
      </Text>
    </div>
  );
}

interface TaxonomyGenerationConfigEditorState {
  activeConfig: TaxonomyGenerationConfig;
  config?: TaxonomyGenerationConfig;
  draftConfig: TaxonomyGenerationConfig | null;
  firstStageInitialCount: number;
  handleRestoreDefaults: () => void;
  handleSave: () => Promise<void>;
  saving: boolean;
  thirdStageInitialCount: number;
  updateDraftConfig: (patch: Partial<TaxonomyGenerationConfig>) => void;
}

function useTaxonomyGenerationConfigEditor({
  onSaved,
}: {
  onSaved?: () => void;
} = {}): TaxonomyGenerationConfigEditorState {
  const { config, mutateConfig } = useTaxonomyGenerationConfig();
  const [draftConfig, setDraftConfig] =
    useState<TaxonomyGenerationConfig | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (config) {
      setDraftConfig(config);
    }
  }, [config]);

  const activeConfig =
    draftConfig || config || DEFAULT_TAXONOMY_GENERATION_CONFIG;
  const firstStageInitialCount =
    activeConfig.first_level_candidate_multiplier *
    activeConfig.first_level_max_count;
  const thirdStageInitialCount =
    activeConfig.third_level_candidate_multiplier *
    activeConfig.third_level_max_count;

  const updateDraftConfig = (patch: Partial<TaxonomyGenerationConfig>) => {
    setDraftConfig((current) => ({
      ...(current || activeConfig),
      ...patch,
    }));
  };

  const handleRestoreDefaults = () => {
    if (!config) {
      return;
    }
    setDraftConfig({
      ...config,
      first_level_candidate_multiplier: 4,
      first_level_max_count: 20,
      third_level_candidate_multiplier: 4,
      third_level_max_count: 6,
      third_level_parallelism: 10,
    });
  };

  const handleSave = async () => {
    if (!draftConfig) {
      return;
    }
    if (
      !draftConfig.l1_l2_prompt_template.trim() ||
      !draftConfig.leaf_prompt_template.trim()
    ) {
      toast.error("提示词模板不能为空");
      return;
    }
    setSaving(true);
    try {
      const savedConfig = await updateTaxonomyGenerationConfig({
        ...draftConfig,
        l1_l2_prompt_template: draftConfig.l1_l2_prompt_template.trim(),
        leaf_prompt_template: draftConfig.leaf_prompt_template.trim(),
      });
      setDraftConfig(savedConfig);
      await mutateConfig(savedConfig, false);
      toast.success("生成参数已保存");
      onSaved?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return {
    activeConfig,
    config,
    draftConfig,
    firstStageInitialCount,
    handleRestoreDefaults,
    handleSave,
    saving,
    thirdStageInitialCount,
    updateDraftConfig,
  };
}

function TaxonomyGenerationConfigFields({
  editor,
}: {
  editor: TaxonomyGenerationConfigEditorState;
}) {
  return (
    <div className="grid w-full grid-cols-[minmax(21rem,0.78fr)_minmax(0,1.22fr)] items-start gap-4">
      <div className="grid min-w-0 grid-rows-[auto_3rem_auto] gap-y-3">
        <Content
          icon={SvgProgressBars}
          title="生成参数"
          sizePreset="main-ui"
          variant="section"
        />

        <div className="grid h-12 grid-cols-2 items-start gap-4 border-b border-border-02 pb-3">
          <GenerationConfigStat
            label="一级/二级候选"
            value={`${editor.firstStageInitialCount}`}
          />
          <GenerationConfigStat
            label="三级每组候选"
            value={`${editor.thirdStageInitialCount}`}
          />
        </div>

        <div>
          <Content
            icon={SvgProgressBars}
            title="数量控制"
            description="控制发散强度、最终保留数量和三级标签生成并发。"
            sizePreset="main-ui"
            variant="section"
          />
          <div className="mt-2 flex flex-col gap-0.5">
            <GenerationNumberField
              label="X 发散倍数"
              description="一级/二级初始候选数量倍数。"
              value={editor.activeConfig.first_level_candidate_multiplier}
              min={1}
              max={20}
              onChange={(value) =>
                editor.updateDraftConfig({
                  first_level_candidate_multiplier: value,
                })
              }
            />
            <GenerationNumberField
              label="Y 最大数量"
              description="一级标签和二级标签的最终数量上限。"
              value={editor.activeConfig.first_level_max_count}
              min={2}
              max={80}
              onChange={(value) =>
                editor.updateDraftConfig({ first_level_max_count: value })
              }
            />
            <GenerationNumberField
              label="M 发散倍数"
              description="三级标签初始候选数量倍数。"
              value={editor.activeConfig.third_level_candidate_multiplier}
              min={1}
              max={20}
              onChange={(value) =>
                editor.updateDraftConfig({
                  third_level_candidate_multiplier: value,
                })
              }
            />
            <GenerationNumberField
              label="N 每组上限"
              description="每个二级标签下的三级标签最终数量上限。"
              value={editor.activeConfig.third_level_max_count}
              min={1}
              max={30}
              onChange={(value) =>
                editor.updateDraftConfig({ third_level_max_count: value })
              }
            />
            <GenerationNumberField
              label="P 并发数"
              description="三级标签生成阶段的并行任务数量。"
              value={editor.activeConfig.third_level_parallelism}
              min={1}
              max={20}
              onChange={(value) =>
                editor.updateDraftConfig({ third_level_parallelism: value })
              }
            />
          </div>
        </div>
      </div>

      <Tabs defaultValue="l1-l2">
        <div className="grid min-w-0 grid-rows-[auto_3rem_auto] gap-y-3">
          <Content
            icon={SvgSparkle}
            title="提示词模板"
            sizePreset="main-ui"
            variant="section"
          />

          <div className="flex h-12 items-start border-b border-border-02 pb-3">
            <Tabs.List variant="underline">
              <Tabs.Trigger value="l1-l2">一级/二级模板</Tabs.Trigger>
              <Tabs.Trigger value="leaf">三级模板</Tabs.Trigger>
            </Tabs.List>
          </div>

          <div>
            <Tabs.Content value="l1-l2" className="pt-0">
              <InputVertical title="L1/L2 Prompt Template" withLabel>
                <InputTextArea
                  value={editor.activeConfig.l1_l2_prompt_template}
                  onChange={(event) =>
                    editor.updateDraftConfig({
                      l1_l2_prompt_template: event.target.value,
                    })
                  }
                  rows={20}
                  maxRows={26}
                  autoResize
                  className="[&_textarea]:font-main-content-mono [&_textarea]:leading-7"
                />
              </InputVertical>
            </Tabs.Content>
            <Tabs.Content value="leaf" className="pt-0">
              <InputVertical title="Leaf Prompt Template" withLabel>
                <InputTextArea
                  value={editor.activeConfig.leaf_prompt_template}
                  onChange={(event) =>
                    editor.updateDraftConfig({
                      leaf_prompt_template: event.target.value,
                    })
                  }
                  rows={20}
                  maxRows={26}
                  autoResize
                  className="[&_textarea]:font-main-content-mono [&_textarea]:leading-7"
                />
              </InputVertical>
            </Tabs.Content>
          </div>
        </div>
      </Tabs>
    </div>
  );
}

function TaxonomyGenerationConfigActions({
  editor,
  disabled = false,
  saveLabel = "保存",
}: {
  editor: TaxonomyGenerationConfigEditorState;
  disabled?: boolean;
  saveLabel?: string;
}) {
  return (
    <>
      <Text font="secondary-body" color="text-03">
        默认参数：X=4，Y=20，M=4，N=6，P=10。
      </Text>
      <div className="flex shrink-0 items-center gap-2">
        <Button
          prominence="secondary"
          variant="action"
          onClick={editor.handleRestoreDefaults}
          disabled={disabled || editor.saving}
        >
          恢复默认参数
        </Button>
        <Button
          icon={editor.saving ? SpinningLoaderIcon : SvgCheck}
          prominence="primary"
          onClick={editor.handleSave}
          disabled={disabled || editor.saving}
        >
          {editor.saving ? "保存中" : saveLabel}
        </Button>
      </div>
    </>
  );
}

function TaxonomyGenerationConfigPanel({
  onSaved,
}: {
  onSaved?: () => void;
} = {}) {
  const editor = useTaxonomyGenerationConfigEditor({ onSaved });

  if (!editor.config && !editor.draftConfig) {
    return <EmptyMessageCard sizePreset="main-ui" title="正在加载生成参数" />;
  }

  return (
    <Section gap={1} alignItems="stretch" justifyContent="start">
      <TaxonomyGenerationConfigFields editor={editor} />
      <div className="flex items-center justify-between gap-3">
        <TaxonomyGenerationConfigActions editor={editor} />
      </div>
    </Section>
  );
}

function TaxonomyGenerationConfigModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const editor = useTaxonomyGenerationConfigEditor({ onSaved: onClose });
  const isLoading = !editor.config && !editor.draftConfig;

  return (
    <Modal open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <Modal.Content width="xl" height="lg" background="gray">
        <DialogPrimitive.Title className="sr-only">
          生成参数
        </DialogPrimitive.Title>
        <Modal.Body>
          <div className="relative w-full pr-8">
            <div className="absolute right-0 top-0 z-10">
              <Button
                icon={SvgX}
                prominence="tertiary"
                size="sm"
                onClick={onClose}
              />
            </div>
            {isLoading ? (
              <EmptyMessageCard sizePreset="main-ui" title="正在加载生成参数" />
            ) : (
              <TaxonomyGenerationConfigFields editor={editor} />
            )}
          </div>
        </Modal.Body>
        <Modal.Footer justifyContent="between">
          <TaxonomyGenerationConfigActions
            disabled={isLoading}
            editor={editor}
            saveLabel="保存参数"
          />
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

export default function TaxonomyPage() {
  return <TaxonomyTemplateDraftPage />;
}

export function TaxonomyTemplateDraftPage() {
  const versions = useTaxonomyVersions();

  return (
    <TaxonomyPageLayout
      route={ADMIN_ROUTES.TAXONOMY_TEMPLATE_DRAFT}
      description="通过提示词快速生成三级标签体系，并在树视图或 JSON 视图中继续编辑。"
      width="full"
    >
      <div className="flex w-full justify-center">
        <div className="w-full max-w-[1480px]">
          <TaxonomyBuilder versions={versions} />
        </div>
      </div>
    </TaxonomyPageLayout>
  );
}

export function TaxonomyImportsPage() {
  const [importModalOpen, setImportModalOpen] = useState(false);
  const { queuedPollActive, startQueuedPoll, stopQueuedPoll } =
    useExpiringTaxonomyImportPoll();
  const dashboard = useTaxonomyDashboard(queuedPollActive);
  const hasActiveTaxonomy = Boolean(dashboard?.taxonomy?.active_version_id);
  const latestTask = getLatestImportTask(dashboard?.recent_tasks);
  const activeTask = taxonomyTaskIsActive(latestTask) ? latestTask : undefined;
  let importStatusTitle = "空闲";
  if (queuedPollActive) {
    importStatusTitle = "后台接收中";
  }
  if (activeTask) {
    importStatusTitle = `${getTaskStatusLabel(activeTask.status)} ${activeTask.processed_docs}/${activeTask.total_docs}`;
  }

  useEffect(() => {
    if (taxonomyDashboardHasActiveProcessing(dashboard)) {
      stopQueuedPoll();
    }
  }, [dashboard, stopQueuedPoll]);

  const handleImportQueued = useCallback(() => {
    startQueuedPoll();
  }, [startQueuedPoll]);

  const handleImportArticles = () => {
    if (!dashboard) {
      toast.error("正在加载标签体系状态，请稍后再试");
      return;
    }
    if (!hasActiveTaxonomy) {
      toast.error("请先创建并生效标签体系，再导入文章");
      return;
    }
    setImportModalOpen(true);
  };

  return (
    <TaxonomyPageLayout
      route={ADMIN_ROUTES.TAXONOMY_IMPORTS}
      description="集中管理入库文章，跟踪 Summary 生成、标签处理与覆盖情况。"
      width="full"
      rightChildren={
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          <Button
            icon={SvgPlus}
            prominence="primary"
            size="lg"
            onClick={handleImportArticles}
          >
            导入文章
          </Button>
          <Tag
            title={importStatusTitle}
            color={activeTask || queuedPollActive ? "blue" : "gray"}
          />
          {!hasActiveTaxonomy && <Tag title="需先启用标签体系" color="amber" />}
        </div>
      }
    >
      <div className="flex w-full justify-center">
        <div className="w-full max-w-[1200px]">
          <ImportedArticlesPanel
            dashboard={dashboard}
            queuedImportActive={queuedPollActive}
          />
        </div>
      </div>
      <ImportArticlesModal
        open={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onImportQueued={handleImportQueued}
      />
    </TaxonomyPageLayout>
  );
}

export function TaxonomyGenerationConfigPage() {
  return (
    <TaxonomyPageLayout
      route={ADMIN_ROUTES.TAXONOMY_GENERATION_CONFIG}
      description="管理标签生成的发散倍数、最终数量上限、三级并发数和系统提示词。"
      width="full"
    >
      <div className="flex w-full justify-center">
        <div className="w-full max-w-[1200px]">
          <TaxonomyGenerationConfigPanel />
        </div>
      </div>
    </TaxonomyPageLayout>
  );
}

export function TaxonomyHistoryPage() {
  const router = useRouter();
  const dashboard = useTaxonomyDashboard();
  const versions = useTaxonomyVersions();

  return (
    <TaxonomyPageLayout
      route={ADMIN_ROUTES.TAXONOMY_HISTORY}
      description="查看当前生效标签体系和所有草稿、生效、已替换版本的历史记录。"
      backButton
      backButtonLabel="返回标签体系"
      onBack={() =>
        router.push(ADMIN_ROUTES.TAXONOMY_TEMPLATE_DRAFT.path as Route)
      }
      width="full"
    >
      <div className="flex w-full justify-center">
        <div className="w-full max-w-[1200px]">
          <ActiveTaxonomyPanel dashboard={dashboard} versions={versions} />
        </div>
      </div>
    </TaxonomyPageLayout>
  );
}

export function TaxonomySummariesPage() {
  const dashboard = useTaxonomyDashboard();

  return (
    <TaxonomyPageLayout
      route={ADMIN_ROUTES.TAXONOMY_SUMMARIES}
      description="Generate and edit document summaries used by taxonomy labels."
    >
      <SummariesPanel dashboard={dashboard} />
    </TaxonomyPageLayout>
  );
}

export function TaxonomyBatchTaggingPage() {
  const dashboard = useTaxonomyDashboard();

  return (
    <TaxonomyPageLayout
      route={ADMIN_ROUTES.TAXONOMY_BATCH_TAGGING}
      description="Apply the active taxonomy to documents and searchable metadata."
    >
      <BatchTaggingPanel dashboard={dashboard} />
    </TaxonomyPageLayout>
  );
}

export function TaxonomyQueryMatchPage() {
  return (
    <TaxonomyPageLayout
      route={ADMIN_ROUTES.TAXONOMY_QUERY_MATCH}
      description="Test query-to-taxonomy matching before enabling filters."
    >
      <QueryMatchPanel />
    </TaxonomyPageLayout>
  );
}
