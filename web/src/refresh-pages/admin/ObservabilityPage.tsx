"use client";

import useSWR from "swr";
import { Button, Card, MessageCard, Text } from "@opal/components";
import * as SettingsLayouts from "@/layouts/settings-layouts";
import { Content, ContentAction } from "@opal/layouts";
import {
  SvgCheckCircle,
  SvgExternalLink,
  SvgEye,
  SvgPlayCircle,
  SvgXCircle,
} from "@opal/icons";
import { toast } from "@/hooks/useToast";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { SWR_KEYS } from "@/lib/swr-keys";

const route = ADMIN_ROUTES.OBSERVABILITY;

interface LangfuseStatusResponse {
  enabled: boolean;
  tracing_provider_initialized: boolean;
  public_key_configured: boolean;
  secret_key_configured: boolean;
  host: string | null;
  ui_host: string | null;
  using_distinct_ui_host: boolean;
}

interface LangfuseSampleTraceResponse {
  sent: boolean;
  trace_count: number;
  message: string;
}

interface OnyxErrorResponse {
  detail?: string;
}

function StatusBadge({ enabled, label }: { enabled: boolean; label: string }) {
  const Icon = enabled ? SvgCheckCircle : SvgXCircle;

  return (
    <div className="flex items-center gap-2">
      <Icon
        size={16}
        className={enabled ? "stroke-status-success-05" : "stroke-text-02"}
      />
      <Text font="secondary-body" color={enabled ? "text-04" : "text-02"}>
        {label}
      </Text>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
      <Text font="secondary-body" color="text-03">
        {label}
      </Text>
      <span className="break-all">
        <Text font="secondary-body" color="text-04">
          {value}
        </Text>
      </span>
    </div>
  );
}

async function sendSampleTraces(): Promise<LangfuseSampleTraceResponse> {
  const response = await fetch(SWR_KEYS.langfuseSampleTraces, {
    method: "POST",
  });

  if (!response.ok) {
    const errorBody = (await response
      .json()
      .catch(() => null)) as OnyxErrorResponse | null;
    throw new Error(
      errorBody?.detail ?? `Failed to send sample traces (${response.status})`
    );
  }

  return response.json();
}

export default function ObservabilityPage() {
  const { data, isLoading, mutate } = useSWR<LangfuseStatusResponse>(
    SWR_KEYS.langfuseStatus,
    errorHandlingFetcher
  );

  const langfuseUrl = data?.ui_host ?? null;
  const canSendSamples = Boolean(
    data?.enabled && data.tracing_provider_initialized
  );

  const handleSendSampleTraces = async () => {
    try {
      const result = await sendSampleTraces();
      await mutate();
      toast.success(`${result.trace_count} sample traces sent to Langfuse.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      toast.error(message);
    }
  };

  return (
    <SettingsLayouts.Root>
      <SettingsLayouts.Header
        icon={route.icon}
        title={route.title}
        description="Review Langfuse tracing status and open the external observability console."
        rightChildren={
          langfuseUrl ? (
            <Button
              variant="action"
              prominence="primary"
              rightIcon={SvgExternalLink}
              href={langfuseUrl}
              target="_blank"
            >
              Open Langfuse
            </Button>
          ) : undefined
        }
        divider
      />
      <SettingsLayouts.Body>
        <Card border="solid" padding="fit">
          <ContentAction
            sizePreset="main-ui"
            variant="section"
            icon={SvgEye}
            title="Langfuse tracing"
            description={
              isLoading
                ? "Loading Langfuse configuration..."
                : data?.enabled
                  ? "Credentials are configured. Use the sample action below to verify the UI."
                  : "Set Langfuse environment variables on the API server and workers to enable tracing."
            }
            padding="md"
            center
            rightChildren={
              <Button
                variant="default"
                prominence="secondary"
                icon={SvgPlayCircle}
                disabled={!canSendSamples}
                onClick={handleSendSampleTraces}
                tooltip={
                  canSendSamples
                    ? "Send synthetic traces through the Onyx tracing processor"
                    : "Langfuse must be configured and initialized first"
                }
              >
                Send Samples
              </Button>
            }
          />
        </Card>

        {data?.using_distinct_ui_host && (
          <MessageCard
            variant="info"
            title="Separate ingestion and browser URLs"
            description="LANGFUSE_HOST is used by backend services for SDK ingestion. LANGFUSE_UI_HOST is used by this admin page for browser navigation."
          />
        )}

        <Card border="solid">
          <div className="flex flex-col gap-4">
            <Content
              sizePreset="main-ui"
              variant="section"
              title="Configuration"
              description="Only safe configuration state is shown here. Secret values are never exposed."
            />

            <div className="grid gap-3 sm:grid-cols-2">
              <StatusBadge
                enabled={Boolean(data?.public_key_configured)}
                label="Public key configured"
              />
              <StatusBadge
                enabled={Boolean(data?.secret_key_configured)}
                label="Secret key configured"
              />
              <StatusBadge
                enabled={Boolean(data?.tracing_provider_initialized)}
                label="Processor initialized"
              />
              <StatusBadge
                enabled={Boolean(data?.ui_host)}
                label="Console URL available"
              />
            </div>

            <div className="flex flex-col gap-3 border-t border-border-02 pt-4">
              <DetailRow
                label="Ingestion host"
                value={data?.host ?? "Not set"}
              />
              <DetailRow
                label="Console URL"
                value={data?.ui_host ?? "Not set"}
              />
            </div>
          </div>
        </Card>

        <Card border="solid">
          <div className="flex flex-col gap-4">
            <Content
              sizePreset="main-ui"
              variant="section"
              title="Local review data"
              description="Send sample traces, then inspect the Langfuse Traces view for chat and indexing examples."
            />
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-08 border border-border-02 p-3">
                <Text font="main-ui-body" color="text-04">
                  Chat sample
                </Text>
                <Text font="secondary-body" color="text-03">
                  flow=chat_response, session=langfuse-local-ui-review,
                  model=gpt-5-mini
                </Text>
              </div>
              <div className="rounded-08 border border-border-02 p-3">
                <Text font="main-ui-body" color="text-04">
                  Indexing sample
                </Text>
                <Text font="secondary-body" color="text-03">
                  flow=contextual_rag_chunk_context,
                  session=langfuse-local-indexing-review, model=gpt-5-mini
                </Text>
              </div>
            </div>
          </div>
        </Card>
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
