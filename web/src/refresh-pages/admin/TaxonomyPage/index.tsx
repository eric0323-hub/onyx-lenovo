"use client";

import type { ChangeEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Tree from "rc-tree";
import type { TreeNodeProps, TreeProps } from "rc-tree";
import useSWR from "swr";
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
import {
  Button,
  Card,
  Divider,
  EmptyMessageCard,
  MessageCard,
  Popover,
  PopoverMenu,
  Tag,
  Text,
} from "@opal/components";
import {
  Card as CardLayout,
  Content,
  InputHorizontal,
  InputVertical,
} from "@opal/layouts";
import {
  SvgBlocks,
  SvgCheck,
  SvgChevronRight,
  SvgClock,
  SvgEdit,
  SvgFileText,
  SvgLoader,
  SvgMoreHorizontal,
  SvgPlus,
  SvgRefreshCw,
  SvgSearch,
  SvgSparkle,
  SvgTag,
  SvgTrash,
  SvgUploadCloud,
} from "@opal/icons";
import type { IconProps } from "@opal/types";
import { toast } from "@/hooks/useToast";
import LineItem from "@/refresh-components/buttons/LineItem";
import {
  activateTaxonomyVersion,
  createTaxonomyDraft,
  fetchDocumentTaxonomyTags,
  generateSummaries,
  generateTaxonomyDraftStream,
  importArticles,
  matchTaxonomyQuery,
  runTagging,
  updateSummary,
} from "./svc";
import {
  DocumentTaxonomyTag,
  DocumentTaxonomySummary,
  TaxonomyDashboard,
  TaxonomyDraftStreamEvent,
  TaxonomyNode,
  TaxonomySearchApplyTo,
  TaxonomySearchDecision,
  TaxonomyTaggingSource,
  TaxonomyTaggingTask,
  TaxonomyVersion,
} from "./types";

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

type TaxonomyNodeListField =
  | "positive_examples"
  | "negative_examples"
  | "keywords"
  | "synonyms";

const TAXONOMY_GENERATION_STORAGE_KEY =
  "onyx.taxonomy.templateDraft.generation.v1";
const TAXONOMY_DASHBOARD_POLL_INTERVAL_MS = 3000;
const TAXONOMY_IMPORT_POST_UPLOAD_POLL_MS = 60_000;

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

function getArticleStage(summary: DocumentTaxonomySummary) {
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

  if (summary.current_label_status) {
    return {
      title: "已打标签",
      description: "文章摘要和标签已生成",
      progress: 100,
      color: "green" as const,
    };
  }

  return {
    title: "等待打标签",
    description: "摘要已生成，等待标签任务处理",
    progress: 65,
    color: "gray" as const,
  };
}

function getDocumentTitle(summary: DocumentTaxonomySummary) {
  return summary.semantic_id?.trim() || "未命名文章";
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
  width = "lg",
  children,
}: {
  route: AdminRouteEntry;
  description: string;
  rightChildren?: ReactNode;
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
  const hasRestoredGenerationRef = useRef(false);

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
      initialNodes = [],
      initialStatus = {
        message: "正在启动标签体系生成",
        progress: 0,
      },
      restored = false,
    }: {
      prompt: string;
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
            parallelism: 10,
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
    hasRestoredGenerationRef.current = true;

    const persistedGeneration = readPersistedTaxonomyGeneration();
    if (!persistedGeneration) {
      return;
    }

    void runTaxonomyGeneration({
      prompt: persistedGeneration.prompt,
      initialNodes: persistedGeneration.nodes,
      initialStatus: {
        message: persistedGeneration.status.message || "正在恢复标签体系生成",
        progress: persistedGeneration.status.progress,
      },
      restored: true,
    });
  }, [runTaxonomyGeneration]);

  const handleGenerate = async () => {
    await runTaxonomyGeneration({ prompt: generationPrompt });
  };

  const handleApplyJson = () => {
    try {
      const nodes = normalizeTaxonomyNodes(
        parseTaxonomyNodesJson(taxonomyJson)
      );
      const validationMessage = getTaxonomyValidationMessage(
        validateTaxonomyNodes(nodes)
      );
      if (validationMessage) {
        throw new Error(validationMessage);
      }
      applyNodes(nodes);
      setEditorView("tree");
      toast.success("已应用 JSON 编辑内容");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "JSON 内容不完整";
      setJsonError(message);
      toast.error(message);
    }
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
    <Section id="taxonomy-builder" className="scroll-mt-24" gap={1}>
      <Card border="solid" rounding="lg">
        <CardLayout.Header>
          <div className="p-2">
            <Content
              icon={SvgSparkle}
              title="提示词生成"
              sizePreset="main-ui"
              variant="section"
            />
          </div>
        </CardLayout.Header>
        <Divider paddingParallel="fit" paddingPerpendicular="fit" />
        <Section className="p-2" gap={0.75} alignItems="stretch">
          <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_7rem] md:items-stretch">
            <InputTextArea
              value={generationPrompt}
              onChange={(e) => setGenerationPrompt(e.target.value)}
              rows={4}
              maxRows={8}
              autoResize
              placeholder="例如：我们是一家制造业企业，知识库包含制度流程、质量管理、设备运维、售后维修、产品手册和安全生产文档。重点关注一线员工查找制度、维修手册和质量问题复盘的场景。"
            />
            <div className="flex items-end [&_.interactive-container]:h-12 md:[&_.interactive-container]:h-16">
              <Button
                icon={isGeneratingTaxonomy ? SpinningLoaderIcon : SvgSparkle}
                prominence="primary"
                onClick={handleGenerate}
                disabled={isGeneratingTaxonomy}
                width="full"
              >
                {isGeneratingTaxonomy ? "生成中" : "生成"}
              </Button>
            </div>
          </div>
          {isGeneratingTaxonomy && (
            <div
              className="flex flex-wrap items-center gap-2 text-status-info-05"
              aria-live="polite"
              role="status"
            >
              <SvgLoader className="size-4 shrink-0 animate-spin" />
              <Text as="p" font="secondary-body" color="inherit">
                {generationStatus?.message ||
                  "正在生成三级标签体系，内容会流式填入下方编辑区。"}
              </Text>
              {generationStatus?.progress != null && (
                <Tag
                  title={`${generationStatus.progress}%`}
                  color="blue"
                  size="sm"
                />
              )}
            </div>
          )}
        </Section>
      </Card>

      <Card border="solid" rounding="lg">
        <CardLayout.Header>
          <div className="flex flex-wrap items-center justify-between gap-2 p-2">
            <Content
              icon={SvgEdit}
              title="编辑"
              description={`一级 ${nodeCounts.l1} · 二级 ${nodeCounts.l2} · 三级 ${nodeCounts.leaf}`}
              sizePreset="main-ui"
              variant="section"
            />
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex items-center gap-1 rounded-08 border border-border-01 bg-background-tint-01 p-0.5">
                <Button
                  prominence={editorView === "tree" ? "secondary" : "tertiary"}
                  size="xs"
                  onClick={() => setEditorView("tree")}
                >
                  树
                </Button>
                <Button
                  prominence={editorView === "json" ? "secondary" : "tertiary"}
                  size="xs"
                  onClick={() => setEditorView("json")}
                >
                  JSON
                </Button>
              </div>
              <Button
                href={ADMIN_ROUTES.TAXONOMY_HISTORY.path}
                icon={SvgClock}
                prominence="secondary"
                size="sm"
              >
                版本历史
              </Button>
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
            <Section gap={0.75}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Button
                  prominence="tertiary"
                  size="sm"
                  icon={SvgCheck}
                  onClick={handleApplyJson}
                >
                  应用编辑
                </Button>
              </div>
              {jsonError && (
                <MessageCard
                  title="JSON 格式错误"
                  description={jsonError}
                  padding="xs"
                />
              )}
              <InputTextArea
                data-testid="taxonomy-json-editor"
                value={taxonomyJson}
                onChange={(e) => {
                  setTaxonomyJson(e.target.value);
                  setJsonError(null);
                  setHasLocalTaxonomyChanges(true);
                }}
                rows={22}
                maxRows={32}
                autoResize
                placeholder="粘贴或编辑 Taxonomy 节点 JSON"
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
    </Section>
  );
}

function ArticleTagList({ tags }: { tags: DocumentTaxonomyTag[] }) {
  const activeTags = tags.filter((tag) => tag.status === "active");

  if (!activeTags.length) {
    return <Tag title="暂无标签" color="gray" />;
  }

  const visibleTags = activeTags.slice(0, 2);
  const hiddenCount = activeTags.length - visibleTags.length;

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-1.5">
      {visibleTags.map((tag) => (
        <Tag
          key={tag.id}
          title={`${tag.full_path_snapshot} · ${(tag.confidence * 100).toFixed(0)}%`}
          color={tag.review_status === "confirmed" ? "green" : "blue"}
        />
      ))}
      {hiddenCount > 0 && <Tag title={`+${hiddenCount}`} color="gray" />}
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

function ArticleProcessingSummary({
  summary,
  tags,
}: {
  summary: DocumentTaxonomySummary;
  tags: DocumentTaxonomyTag[];
}) {
  const stage = getArticleStage(summary);

  return (
    <div className="grid grid-cols-[minmax(0,2fr)_minmax(140px,1fr)_150px] items-center gap-3 border-t border-border-01 pt-1.5">
      <div className="col-span-2 grid grid-cols-[minmax(170px,auto)_minmax(140px,1fr)_2.75rem] items-center gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Tag title={stage.title} color={stage.color} />
          <Text as="p" font="secondary-body" color="text-03" maxLines={1}>
            {stage.description}
          </Text>
        </div>
        <div
          className="h-1.5 overflow-hidden rounded-full bg-background-tint-02"
          aria-label={stage.title}
        >
          <div
            className="h-full rounded-full bg-theme-blue-05 transition-all duration-300"
            style={{ width: `${stage.progress}%` }}
          />
        </div>
        <Text font="main-ui-action" color="text-05" nowrap>
          {`${stage.progress}%`}
        </Text>
      </div>

      <div className="flex min-w-0 items-center justify-end gap-2">
        <Text as="span" font="figure-small-label" color="text-03" nowrap>
          标签
        </Text>
        <ArticleTagList tags={tags} />
      </div>
    </div>
  );
}

function ArticleSummaryStatus({
  summary,
  onEditSummary,
}: {
  summary: DocumentTaxonomySummary;
  onEditSummary: (summary: DocumentTaxonomySummary) => void;
}) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-1.5">
      <div className="flex min-w-0 items-center gap-1.5">
        <Tag
          title={getSummaryStatusLabel(summary.status)}
          color={getSummaryStatusColor(summary.status)}
        />
        <Text font="secondary-body" color="text-03" maxLines={1}>
          {summary.is_manual ? "人工" : "AI"}
        </Text>
      </div>
      <Popover>
        <Popover.Trigger asChild>
          <Button
            icon={SvgMoreHorizontal}
            prominence="tertiary"
            size="sm"
            tooltip="Summary 操作"
          />
        </Popover.Trigger>
        <Popover.Content side="bottom" align="end" width="sm">
          <PopoverMenu>
            {[
              <LineItem
                key="edit-summary"
                icon={SvgEdit}
                onClick={() => onEditSummary(summary)}
              >
                查看 / 编辑 Summary
              </LineItem>,
            ]}
          </PopoverMenu>
        </Popover.Content>
      </Popover>
    </div>
  );
}

function ArticleFileNameCell({
  summary,
}: {
  summary: DocumentTaxonomySummary;
}) {
  return (
    <div className="min-w-0">
      <Text as="p" font="main-ui-action" color="text-05" maxLines={1}>
        {getDocumentTitle(summary)}
      </Text>
    </div>
  );
}

function ArticleTimeCell({ summary }: { summary: DocumentTaxonomySummary }) {
  return (
    <div className="min-w-0">
      <Text as="p" font="secondary-body" color="text-03" maxLines={1}>
        {formatDate(summary.generated_at || summary.updated_at)}
      </Text>
    </div>
  );
}

function SummaryEditorModal({
  summary,
  onClose,
}: {
  summary: DocumentTaxonomySummary | null;
  onClose: () => void;
}) {
  const tags = useDocumentTaxonomyTags(summary?.document_id ?? "");
  const [value, setValue] = useState(summary?.summary ?? "");
  const [lastSavedValue, setLastSavedValue] = useState(summary?.summary ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const nextValue = summary?.summary ?? "";
    setValue(nextValue);
    setLastSavedValue(nextValue);
  }, [summary?.document_id, summary?.summary]);

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

  return (
    <Modal open={!!summary} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <Modal.Content width="lg" height="lg" background="gray">
        <Modal.Header
          icon={SvgFileText}
          title="编辑 Summary"
          description={
            summary
              ? `${getDocumentTitle(summary)} · 保存后会自动重新打标签`
              : "保存后会自动重新打标签"
          }
          onClose={handleClose}
        />
        <Modal.Body>
          {summary && (
            <Section gap={1} alignItems="stretch">
              <Card border="solid" rounding="md" padding="md">
                <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4">
                  <div className="min-w-0">
                    <Text font="main-ui-action" color="text-05" maxLines={2}>
                      {getDocumentTitle(summary)}
                    </Text>
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
                      title={summary.current_label_status || "标签待生成"}
                      color="gray"
                    />
                  </div>
                </div>
              </Card>

              <InputVertical title="Summary" withLabel>
                <InputTextArea
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  rows={8}
                  maxRows={16}
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
                      {`${tags.filter((tag) => tag.status === "active").length} 个有效标签`}
                    </Text>
                  </div>
                  <ArticleTagList tags={tags} />
                </div>
              </Card>
            </Section>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button prominence="secondary" onClick={handleClose}>
            关闭
          </Button>
          <Button
            icon={saving ? SpinningLoaderIcon : SvgCheck}
            prominence="primary"
            onClick={handleSave}
            disabled={!summary || saving || value === lastSavedValue}
          >
            {saving ? "保存中" : "保存 Summary"}
          </Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

function ImportedArticleRow({
  summary,
  onEditSummary,
}: {
  summary: DocumentTaxonomySummary;
  onEditSummary: (summary: DocumentTaxonomySummary) => void;
}) {
  const tags = useDocumentTaxonomyTags(summary.document_id);

  return (
    <div className="flex flex-col gap-1.5 border-b border-border-01 px-4 py-2.5 last:border-b-0">
      <div className="grid grid-cols-[minmax(0,2fr)_minmax(140px,1fr)_150px] items-center gap-3">
        <ArticleFileNameCell summary={summary} />
        <ArticleTimeCell summary={summary} />
        <ArticleSummaryStatus summary={summary} onEditSummary={onEditSummary} />
      </div>

      <ArticleProcessingSummary summary={summary} tags={tags} />
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
}: {
  summaries: DocumentTaxonomySummary[];
}) {
  const [editingSummary, setEditingSummary] =
    useState<DocumentTaxonomySummary | null>(null);

  return (
    <>
      <Card border="solid" rounding="lg" padding="fit">
        <div className="flex min-w-0 flex-col">
          <div className="border-b border-border-01 px-4 py-4">
            <ArticleListHeader count={summaries.length} />
          </div>
          <div className="grid grid-cols-[minmax(0,2fr)_minmax(140px,1fr)_150px] items-center gap-3 border-b border-border-01 bg-background-tint-01 px-4 py-2.5">
            <Text font="figure-small-label" color="text-03">
              文件名
            </Text>
            <Text font="figure-small-label" color="text-03">
              生成/更新时间
            </Text>
            <Text font="figure-small-label" color="text-03">
              Summary
            </Text>
          </div>
          {summaries.map((summary) => (
            <ImportedArticleRow
              key={summary.document_id}
              summary={summary}
              onEditSummary={setEditingSummary}
            />
          ))}
        </div>
      </Card>
      <SummaryEditorModal
        summary={editingSummary}
        onClose={() => setEditingSummary(null)}
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
        <ImportedArticlesList summaries={summaries} />
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
            title={summary.current_label_status || summary.status}
            color={summary.status === "complete" ? "green" : "amber"}
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

  return (
    <Section id="active-taxonomy" className="scroll-mt-24" gap={1}>
      <div className="grid gap-3 md:grid-cols-3">
        <StatCard
          title="Coverage"
          value={`${dashboard?.coverage.coverage_percent?.toFixed(1) ?? "0.0"}%`}
          detail={`${dashboard?.coverage.labeled_documents ?? 0}/${dashboard?.coverage.total_documents ?? 0} documents labeled`}
        />
        <StatCard
          title="Active Version"
          value={activeVersion ? `v${activeVersion.version_number}` : "None"}
          detail={
            activeVersion
              ? `${activeCounts?.leaf ?? 0} leaves · ${formatDate(activeVersion.effective_at)}`
              : "Create and activate a draft to enable tagging"
          }
        />
        <StatCard
          title="Versions"
          value={String(versions.length)}
          detail={`${versions.filter((version) => version.status === "draft").length} drafts waiting`}
        />
      </div>

      <Card border="solid" rounding="lg">
        <CardLayout.Header>
          <div className="p-2">
            <Content
              icon={SvgBlocks}
              title="当前生效版本"
              description={
                activeVersion
                  ? dashboard?.taxonomy?.name || "Enterprise Knowledge Taxonomy"
                  : "暂无生效标签体系版本"
              }
              sizePreset="main-ui"
              variant="section"
            />
          </div>
        </CardLayout.Header>
        <Divider paddingParallel="fit" paddingPerpendicular="fit" />
        {activeVersion ? (
          <Section gap={0.75}>
            {activeVersion.health_summary && (
              <MessageCard
                title="健康检查摘要"
                description={JSON.stringify(activeVersion.health_summary)}
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
              title="版本历史"
              description="查看每次保存的版本、修改说明、来源和创建时间。草稿需要设为生效后才会用于打标和检索过滤。"
              sizePreset="main-ui"
              variant="section"
            />
          </div>
        </CardLayout.Header>
        <Divider paddingParallel="fit" paddingPerpendicular="fit" />
        <Section gap={0.5}>
          {versions.length ? (
            versions.map((version) => (
              <Card key={version.id} border="solid" rounding="md">
                <InputHorizontal
                  title={`v${version.version_number} · ${version.status}`}
                  description={getVersionHistoryDescription(version)}
                  withLabel
                >
                  <Tag
                    title={version.source}
                    color={version.status === "active" ? "green" : "gray"}
                  />
                </InputHorizontal>
              </Card>
            ))
          ) : (
            <EmptyMessageCard sizePreset="main-ui" title="暂无版本历史" />
          )}
        </Section>
      </Card>
    </Section>
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
    >
      <TaxonomyBuilder versions={versions} />
    </TaxonomyPageLayout>
  );
}

export function TaxonomyImportsPage() {
  const [queuedPollUntil, setQueuedPollUntil] = useState<number | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const queuedPollActive =
    queuedPollUntil !== null && Date.now() < queuedPollUntil;
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
    if (!queuedPollUntil) {
      return;
    }
    if (
      Date.now() >= queuedPollUntil ||
      taxonomyDashboardHasActiveProcessing(dashboard)
    ) {
      setQueuedPollUntil(null);
    }
  }, [dashboard, queuedPollUntil]);

  const handleImportQueued = useCallback(() => {
    setQueuedPollUntil(Date.now() + TAXONOMY_IMPORT_POST_UPLOAD_POLL_MS);
  }, []);

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

export function TaxonomyHistoryPage() {
  const dashboard = useTaxonomyDashboard();
  const versions = useTaxonomyVersions();

  return (
    <TaxonomyPageLayout
      route={ADMIN_ROUTES.TAXONOMY_HISTORY}
      description="查看当前生效标签体系和所有草稿、生效、已替换版本的历史记录。"
    >
      <ActiveTaxonomyPanel dashboard={dashboard} versions={versions} />
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
