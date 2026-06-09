"use client";

import { useMemo, useState, type ReactNode } from "react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { Button, Checkbox, Text } from "@opal/components";
import {
  SvgAlertCircle,
  SvgCheck,
  SvgCheckCircle,
  SvgPlayCircle,
  SvgX,
} from "@opal/icons";
import { toast } from "@/hooks/useToast";
import { useDocumentSets } from "@/lib/hooks/useDocumentSets";
import InputNumber from "@/refresh-components/inputs/InputNumber";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import InputTextArea from "@/refresh-components/inputs/InputTextArea";
import InputTypeIn from "@/refresh-components/inputs/InputTypeIn";
import {
  createExternalRetrievalSource,
  testExternalRetrievalConfig,
  updateExternalRetrievalSource,
} from "./lib";
import {
  ExternalRetrievalAdapterType,
  ExternalRetrievalAuthType,
  ExternalRetrievalCallStrategy,
  ExternalRetrievalConfig,
  ExternalRetrievalRequestMode,
  ExternalRetrievalSourceUpsertRequest,
  ExternalRetrievalSourceView,
  ExternalRetrievalTestResult,
} from "./types";

const DEFAULT_FIELD_MAPPING = {
  title: ["$.title", "$.article_title", "$.article.title"],
  content: ["$.content", "$.evidence_text", "$.article", "$.article.body"],
  url: ["$.url", "$.article_url", "$.link"],
  score: ["$.score", "$.relevance_score"],
  confidence: ["$.confidence"],
  source_id: ["$.source_id", "$.article_id", "$.id"],
};

const OPTIONAL_MAPPING_FIELDS = [
  { key: "url", label: "URL paths" },
  { key: "score", label: "Score paths" },
  { key: "confidence", label: "Confidence paths" },
  { key: "source_id", label: "Source ID paths" },
] as const;

interface SelectOption<T extends string> {
  value: T;
  label: string;
  description?: string;
}

const ADAPTER_OPTIONS: SelectOption<ExternalRetrievalAdapterType>[] = [
  {
    value: "ontology",
    label: "Ontology",
    description: "External ontology retrieval adapter.",
  },
  {
    value: "http_json",
    label: "HTTP JSON",
    description: "Normalize results from a JSON HTTP endpoint.",
  },
];

const AUTH_OPTIONS: SelectOption<ExternalRetrievalAuthType>[] = [
  { value: "none", label: "None" },
  { value: "bearer", label: "Bearer token" },
  { value: "api_key_header", label: "API key header" },
  { value: "basic", label: "Basic auth" },
];

const REQUEST_MODE_OPTIONS: SelectOption<ExternalRetrievalRequestMode>[] = [
  { value: "simple", label: "Simple" },
  { value: "standard", label: "Standard" },
  { value: "custom_template", label: "Custom template" },
];

const CALL_STRATEGY_OPTIONS: SelectOption<ExternalRetrievalCallStrategy>[] = [
  { value: "original_query_once", label: "Original query once" },
  { value: "semantic_query_once", label: "Semantic query once" },
  { value: "per_expanded_query", label: "Per expanded query" },
];

function defaultConfig(): ExternalRetrievalConfig {
  return {
    endpoint: "http://127.0.0.1:8000/api/retrieval/search",
    method: "POST",
    headers: {},
    request_mode: "simple",
    request_template: null,
    result_path: null,
    field_mapping: DEFAULT_FIELD_MAPPING,
    max_content_chars: 6000,
    score_scale: null,
    allow_localhost: true,
    strict_result_validation: false,
  };
}

function textToPaths(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function pathsToText(paths: string[] | undefined): string {
  return (paths || []).join("\n");
}

function toNumberOrNull(value: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function SelectField<T extends string>({
  value,
  onValueChange,
  options,
  disabled,
}: {
  value: T;
  onValueChange: (value: T) => void;
  options: SelectOption<T>[];
  disabled?: boolean;
}) {
  return (
    <InputSelect
      value={value}
      onValueChange={(nextValue) => onValueChange(nextValue as T)}
      disabled={disabled}
    >
      <InputSelect.Trigger />
      <InputSelect.Content>
        {options.map((option) => (
          <InputSelect.Item
            key={option.value}
            value={option.value}
            description={option.description}
          >
            {option.label}
          </InputSelect.Item>
        ))}
      </InputSelect.Content>
    </InputSelect>
  );
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="grid grid-cols-[188px_minmax(0,1fr)] gap-6 border-b border-border-02 py-8 first:pt-0 last:border-b-0">
      <div>
        <Text as="h2" font="heading-h3">
          {title}
        </Text>
        <div className="pt-2">
          <Text as="p" font="secondary-body" color="text-03">
            {description}
          </Text>
        </div>
      </div>
      <div className="space-y-5">{children}</div>
    </section>
  );
}

function FieldRow({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[142px_minmax(0,1fr)] items-start gap-5">
      <div className="pt-2">
        <Text as="p" font="secondary-action">
          {label}
        </Text>
        {description && (
          <div className="pt-1">
            <Text as="p" font="secondary-body" color="text-03">
              {description}
            </Text>
          </div>
        )}
      </div>
      <div>{children}</div>
    </div>
  );
}

function FieldGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Text as="p" font="secondary-action">
        {label}
      </Text>
      {children}
    </div>
  );
}

function TwoColumn({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-5">{children}</div>;
}

function InlineCheckbox({
  id,
  checked,
  onCheckedChange,
  label,
  description,
}: {
  id: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="pt-0.5">
        <Checkbox
          id={id}
          checked={checked}
          onCheckedChange={onCheckedChange}
          aria-label={label}
        />
      </div>
      <label htmlFor={id} className="min-w-0 cursor-pointer">
        <Text as="p" font="secondary-action">
          {label}
        </Text>
        {description && (
          <div className="pt-1">
            <Text as="p" font="secondary-body" color="text-03">
              {description}
            </Text>
          </div>
        )}
      </label>
    </div>
  );
}

function TestPanel({
  testQuery,
  setTestQuery,
  includeRaw,
  setIncludeRaw,
  isTesting,
  testResult,
  onRunTest,
}: {
  testQuery: string;
  setTestQuery: (value: string) => void;
  includeRaw: boolean;
  setIncludeRaw: (value: boolean) => void;
  isTesting: boolean;
  testResult: ExternalRetrievalTestResult | null;
  onRunTest: () => void;
}) {
  const StatusIcon = testResult?.success ? SvgCheckCircle : SvgAlertCircle;
  const statusClass = testResult?.success
    ? "text-status-success-05"
    : "text-status-danger-05";

  return (
    <aside className="sticky top-6 rounded-08 border border-border-02 bg-background-neutral-00 p-4">
      <Text as="h2" font="heading-h3">
        Test connection
      </Text>
      <div className="pt-2">
        <Text as="p" font="secondary-body" color="text-03">
          Runs against the current form values before you save.
        </Text>
      </div>

      <div className="space-y-4 pt-5">
        <FieldGroup label="Test query">
          <InputTextArea
            rows={4}
            value={testQuery}
            onChange={(e) => setTestQuery(e.target.value)}
          />
        </FieldGroup>

        <InlineCheckbox
          id="external-retrieval-include-raw"
          checked={includeRaw}
          onCheckedChange={setIncludeRaw}
          label="Include raw response"
        />

        <Button
          icon={SvgPlayCircle}
          prominence="secondary"
          width="full"
          onClick={onRunTest}
          disabled={isTesting}
        >
          {isTesting ? "Testing..." : "Test connection"}
        </Button>

        {testResult && (
          <div className="border-t border-border-02 pt-4">
            <div className="flex items-center gap-2">
              <StatusIcon size={18} className={statusClass} />
              <div className={statusClass}>
                <Text font="secondary-action" color="inherit">
                  {testResult.success ? "Succeeded" : "Failed"}
                </Text>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3 pt-3">
              <Metric
                label="Latency"
                value={`${testResult.latency_ms ?? 0}ms`}
              />
              <Metric
                label="Valid"
                value={String(testResult.normalized_results.length)}
              />
              <Metric
                label="Invalid"
                value={String(testResult.invalid_results.length)}
              />
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <Text as="p" font="secondary-body" color="text-03">
        {label}
      </Text>
      <div className="pt-1">
        <Text as="p" font="secondary-action">
          {value}
        </Text>
      </div>
    </div>
  );
}

function ResultPreview({ result }: { result: ExternalRetrievalTestResult }) {
  const firstResults = result.normalized_results.slice(0, 3);
  const firstInvalidResults = result.invalid_results.slice(0, 3);

  return (
    <div className="border-t border-border-02 pt-5">
      <div className="flex items-center justify-between">
        <Text as="h3" font="heading-h3">
          Test result
        </Text>
        <div
          className={
            result.success ? "text-status-success-05" : "text-status-danger-05"
          }
        >
          <Text font="secondary-action" color="inherit">
            {result.success ? "Success" : result.error_code || "Failed"}
          </Text>
        </div>
      </div>

      {result.message && (
        <div className="pt-3">
          <Text as="p" font="secondary-body" color="text-03">
            {result.message}
          </Text>
        </div>
      )}

      {firstResults.length > 0 && (
        <div className="space-y-3 pt-4">
          {firstResults.map((item) => (
            <div
              key={item.document_id}
              className="border-t border-border-02 pt-3"
            >
              <Text as="p" font="main-ui-action">
                {item.title}
              </Text>
              <div className="pt-1">
                <Text as="p" font="secondary-body" color="text-03" maxLines={2}>
                  {item.content}
                </Text>
              </div>
              <div className="pt-1">
                <Text as="p" font="secondary-body" color="text-03">
                  {`score ${item.score.toFixed(3)}${
                    item.confidence != null
                      ? ` - confidence ${item.confidence.toFixed(3)}`
                      : ""
                  }`}
                </Text>
              </div>
            </div>
          ))}
        </div>
      )}

      {firstInvalidResults.length > 0 && (
        <div className="space-y-2 pt-4">
          {firstInvalidResults.map((item) => (
            <div key={item.index} className="text-status-danger-05">
              <Text as="p" font="secondary-body" color="inherit">
                {`Result ${item.index + 1}: ${item.reason}`}
              </Text>
            </div>
          ))}
        </div>
      )}

      {result.raw_response != null && (
        <pre className="mt-4 max-h-80 overflow-auto rounded-08 bg-background-neutral-02 p-3 text-xs text-text-04">
          {JSON.stringify(result.raw_response, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function ExternalRetrievalForm({
  existingSource,
  testOnly = false,
}: {
  existingSource?: ExternalRetrievalSourceView;
  testOnly?: boolean;
}) {
  const router = useRouter();
  const { documentSets } = useDocumentSets();
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] =
    useState<ExternalRetrievalTestResult | null>(null);
  const [testQuery, setTestQuery] = useState("你的问题");
  const [includeRaw, setIncludeRaw] = useState(false);

  const [name, setName] = useState(
    existingSource?.name ?? "Engineering Ontology"
  );
  const [description, setDescription] = useState(
    existingSource?.description ?? "External ontology retrieval endpoint"
  );
  const [enabled, setEnabled] = useState(existingSource?.enabled ?? false);
  const [adapterType, setAdapterType] = useState<ExternalRetrievalAdapterType>(
    existingSource?.adapter_type ?? "ontology"
  );
  const [authType, setAuthType] = useState<ExternalRetrievalAuthType>(
    existingSource?.auth.type ?? "none"
  );
  const [token, setToken] = useState(existingSource?.auth.token ?? "");
  const [apiKeyHeader, setApiKeyHeader] = useState(
    existingSource?.auth.api_key_header ?? "X-API-Key"
  );
  const [apiKey, setApiKey] = useState(existingSource?.auth.api_key ?? "");
  const [username, setUsername] = useState(existingSource?.auth.username ?? "");
  const [password, setPassword] = useState(existingSource?.auth.password ?? "");
  const [config, setConfig] = useState<ExternalRetrievalConfig>(
    existingSource?.config ?? defaultConfig()
  );
  const [timeoutMs, setTimeoutMs] = useState(
    existingSource?.timeout_ms ?? 3000
  );
  const [maxResults, setMaxResults] = useState(
    existingSource?.max_results ?? 10
  );
  const [sourceWeight, setSourceWeight] = useState(
    existingSource?.source_weight ?? 0.6
  );
  const [minConfidence, setMinConfidence] = useState(
    existingSource?.min_confidence?.toString() ?? ""
  );
  const [callStrategy, setCallStrategy] =
    useState<ExternalRetrievalCallStrategy>(
      existingSource?.call_strategy ?? "original_query_once"
    );
  const [documentSetIds, setDocumentSetIds] = useState<number[]>(
    existingSource?.document_sets.map((set) => set.id) ?? []
  );

  const request = useMemo<ExternalRetrievalSourceUpsertRequest>(() => {
    const authChanged =
      !existingSource ||
      authType !== existingSource.auth.type ||
      token !== (existingSource.auth.token ?? "") ||
      apiKey !== (existingSource.auth.api_key ?? "") ||
      apiKeyHeader !== (existingSource.auth.api_key_header ?? "X-API-Key") ||
      username !== (existingSource.auth.username ?? "") ||
      password !== (existingSource.auth.password ?? "");

    return {
      name,
      description,
      adapter_type: adapterType,
      enabled,
      auth: {
        type: authType,
        token: authType === "bearer" ? token : null,
        api_key_header: authType === "api_key_header" ? apiKeyHeader : null,
        api_key: authType === "api_key_header" ? apiKey : null,
        username: authType === "basic" ? username : null,
        password: authType === "basic" ? password : null,
      },
      auth_changed: authChanged,
      config,
      timeout_ms: timeoutMs,
      max_results: maxResults,
      source_weight: sourceWeight,
      min_confidence: toNumberOrNull(minConfidence),
      call_strategy: callStrategy,
      document_set_ids: documentSetIds,
    };
  }, [
    adapterType,
    apiKey,
    apiKeyHeader,
    authType,
    callStrategy,
    config,
    description,
    documentSetIds,
    enabled,
    existingSource,
    maxResults,
    minConfidence,
    name,
    password,
    sourceWeight,
    timeoutMs,
    token,
    username,
  ]);

  const runTest = async () => {
    setIsTesting(true);
    try {
      const result =
        existingSource && testOnly
          ? await import("./lib").then((lib) =>
              lib.testExternalRetrievalSource(
                existingSource.id,
                testQuery,
                maxResults,
                includeRaw
              )
            )
          : await testExternalRetrievalConfig(
              request,
              testQuery,
              maxResults,
              includeRaw
            );
      setTestResult(result);
      if (result.success) {
        toast.success("External retrieval test completed.");
      } else {
        toast.error(result.message || "External retrieval test failed.");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Test failed.");
    } finally {
      setIsTesting(false);
    }
  };

  const save = async () => {
    setIsSaving(true);
    try {
      const saved = existingSource
        ? await updateExternalRetrievalSource(existingSource.id, request)
        : await createExternalRetrievalSource(request);
      toast.success("External retrieval source saved.");
      router.push(`/admin/external-retrieval/${saved.id}` as Route);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Save failed.");
    } finally {
      setIsSaving(false);
    }
  };

  const updateMapping = (field: string, value: string) => {
    setConfig((current) => ({
      ...current,
      field_mapping: {
        ...current.field_mapping,
        [field]: textToPaths(value),
      },
    }));
  };

  const handleCancel = () => {
    const destination =
      testOnly && existingSource
        ? `/admin/external-retrieval/${existingSource.id}`
        : "/admin/external-retrieval";
    router.push(destination as Route);
  };

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <div className="grid grid-cols-[minmax(0,1fr)_280px] items-start gap-6">
        <div className="rounded-08 border border-border-02 bg-background-neutral-00 px-6">
          <Section
            title="Connection"
            description="Identify the source, endpoint, and credentials used for external retrieval."
          >
            <TwoColumn>
              <FieldGroup label="Name">
                <InputTypeIn
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  showClearButton={false}
                />
              </FieldGroup>
              <FieldGroup label="Adapter">
                <SelectField
                  value={adapterType}
                  onValueChange={setAdapterType}
                  options={ADAPTER_OPTIONS}
                />
              </FieldGroup>
            </TwoColumn>

            <FieldRow label="Description">
              <InputTypeIn
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                showClearButton={false}
              />
            </FieldRow>

            <FieldRow label="Endpoint">
              <InputTypeIn
                value={config.endpoint}
                onChange={(e) =>
                  setConfig({ ...config, endpoint: e.target.value })
                }
                showClearButton={false}
              />
            </FieldRow>

            <TwoColumn>
              <FieldGroup label="Auth type">
                <SelectField
                  value={authType}
                  onValueChange={setAuthType}
                  options={AUTH_OPTIONS}
                />
              </FieldGroup>
              <FieldGroup label="Timeout">
                <InputNumber
                  value={timeoutMs}
                  onChange={(value) => setTimeoutMs(value ?? 0)}
                  min={0}
                  step={500}
                />
              </FieldGroup>
            </TwoColumn>

            {authType === "bearer" && (
              <FieldRow label="Bearer token">
                <InputTypeIn
                  type="password"
                  value={token || ""}
                  onChange={(e) => setToken(e.target.value)}
                  showClearButton={false}
                />
              </FieldRow>
            )}
            {authType === "api_key_header" && (
              <TwoColumn>
                <FieldGroup label="Header name">
                  <InputTypeIn
                    value={apiKeyHeader || ""}
                    onChange={(e) => setApiKeyHeader(e.target.value)}
                    showClearButton={false}
                  />
                </FieldGroup>
                <FieldGroup label="API key">
                  <InputTypeIn
                    type="password"
                    value={apiKey || ""}
                    onChange={(e) => setApiKey(e.target.value)}
                    showClearButton={false}
                  />
                </FieldGroup>
              </TwoColumn>
            )}
            {authType === "basic" && (
              <TwoColumn>
                <FieldGroup label="Username">
                  <InputTypeIn
                    value={username || ""}
                    onChange={(e) => setUsername(e.target.value)}
                    showClearButton={false}
                  />
                </FieldGroup>
                <FieldGroup label="Password">
                  <InputTypeIn
                    type="password"
                    value={password || ""}
                    onChange={(e) => setPassword(e.target.value)}
                    showClearButton={false}
                  />
                </FieldGroup>
              </TwoColumn>
            )}

            <div className="grid grid-cols-2 gap-5">
              <InlineCheckbox
                id="external-retrieval-enabled"
                checked={enabled}
                onCheckedChange={setEnabled}
                label="Enabled"
                description="Query this source during retrieval."
              />
              <InlineCheckbox
                id="external-retrieval-localhost"
                checked={config.allow_localhost}
                onCheckedChange={(checked) =>
                  setConfig({ ...config, allow_localhost: checked })
                }
                label="Allow localhost"
                description="Useful for local development endpoints."
              />
            </div>
          </Section>

          <Section
            title="Response mapping"
            description="Map external JSON fields into normalized search results."
          >
            <TwoColumn>
              <FieldGroup label="Request mode">
                <SelectField
                  value={config.request_mode}
                  onValueChange={(requestMode) =>
                    setConfig({ ...config, request_mode: requestMode })
                  }
                  options={REQUEST_MODE_OPTIONS}
                />
              </FieldGroup>
              <FieldGroup label="Result path">
                <InputTypeIn
                  value={config.result_path ?? ""}
                  placeholder="$.results"
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      result_path: e.target.value || null,
                    })
                  }
                  showClearButton={false}
                />
              </FieldGroup>
            </TwoColumn>

            <FieldRow
              label="Title paths"
              description="One JSONPath per line, checked in order."
            >
              <InputTextArea
                rows={3}
                className="font-mono"
                value={pathsToText(config.field_mapping.title)}
                onChange={(e) => updateMapping("title", e.target.value)}
              />
            </FieldRow>

            <FieldRow
              label="Content paths"
              description="The first matching field becomes result body text."
            >
              <InputTextArea
                rows={3}
                className="font-mono"
                value={pathsToText(config.field_mapping.content)}
                onChange={(e) => updateMapping("content", e.target.value)}
              />
            </FieldRow>

            <div className="grid grid-cols-2 gap-5">
              {OPTIONAL_MAPPING_FIELDS.map((field) => (
                <FieldGroup key={field.key} label={field.label}>
                  <InputTextArea
                    rows={3}
                    className="font-mono"
                    value={pathsToText(config.field_mapping[field.key])}
                    onChange={(e) => updateMapping(field.key, e.target.value)}
                  />
                </FieldGroup>
              ))}
            </div>
          </Section>

          <Section
            title="Retrieval behavior"
            description="Control result limits, ranking weight, and availability scope."
          >
            <div className="grid grid-cols-3 gap-5">
              <FieldGroup label="Max results">
                <InputNumber
                  value={maxResults}
                  onChange={(value) => setMaxResults(value ?? 0)}
                  min={0}
                />
              </FieldGroup>
              <FieldGroup label="Max content chars">
                <InputNumber
                  value={config.max_content_chars}
                  onChange={(value) =>
                    setConfig({
                      ...config,
                      max_content_chars: value ?? 0,
                    })
                  }
                  min={0}
                  step={500}
                />
              </FieldGroup>
              <FieldGroup label="Source weight">
                <InputTypeIn
                  value={String(sourceWeight)}
                  onChange={(e) => {
                    const parsed = Number(e.target.value);
                    setSourceWeight(Number.isFinite(parsed) ? parsed : 0);
                  }}
                  showClearButton={false}
                />
              </FieldGroup>
              <FieldGroup label="Min confidence">
                <InputTypeIn
                  value={minConfidence}
                  onChange={(e) => setMinConfidence(e.target.value)}
                  showClearButton={false}
                />
              </FieldGroup>
              <FieldGroup label="Score scale">
                <InputTypeIn
                  value={config.score_scale ?? ""}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      score_scale: toNumberOrNull(e.target.value),
                    })
                  }
                  showClearButton={false}
                />
              </FieldGroup>
              <FieldGroup label="Call strategy">
                <SelectField
                  value={callStrategy}
                  onValueChange={setCallStrategy}
                  options={CALL_STRATEGY_OPTIONS}
                />
              </FieldGroup>
            </div>

            <InlineCheckbox
              id="external-retrieval-strict-validation"
              checked={config.strict_result_validation}
              onCheckedChange={(checked) =>
                setConfig({
                  ...config,
                  strict_result_validation: checked,
                })
              }
              label="Strict result validation"
              description="Reject malformed results instead of using fallbacks."
            />

            <FieldRow
              label="Document sets"
              description="Leave empty to make this source available globally."
            >
              <div className="grid grid-cols-2 gap-3">
                {documentSets.length === 0 && (
                  <Text as="p" font="secondary-body" color="text-03">
                    No document sets are available.
                  </Text>
                )}
                {documentSets.map((documentSet) => (
                  <InlineCheckbox
                    key={documentSet.id}
                    id={`external-retrieval-document-set-${documentSet.id}`}
                    checked={documentSetIds.includes(documentSet.id)}
                    onCheckedChange={(checked) => {
                      setDocumentSetIds((current) =>
                        checked
                          ? [...current, documentSet.id]
                          : current.filter((id) => id !== documentSet.id)
                      );
                    }}
                    label={documentSet.name}
                  />
                ))}
              </div>
            </FieldRow>

            {testResult && <ResultPreview result={testResult} />}
          </Section>
        </div>

        <TestPanel
          testQuery={testQuery}
          setTestQuery={setTestQuery}
          includeRaw={includeRaw}
          setIncludeRaw={setIncludeRaw}
          isTesting={isTesting}
          testResult={testResult}
          onRunTest={runTest}
        />
      </div>

      <div className="sticky bottom-0 z-20 mt-6 border-t border-border-02 bg-background-tint-01/95 py-3 backdrop-blur">
        <div className="flex items-center justify-end gap-2">
          <Button icon={SvgX} prominence="tertiary" onClick={handleCancel}>
            {testOnly ? "Back" : "Cancel"}
          </Button>
          {!testOnly && (
            <Button icon={SvgCheck} onClick={save} disabled={isSaving}>
              {isSaving ? "Saving..." : "Save"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
