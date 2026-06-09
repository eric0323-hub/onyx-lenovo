"use client";

import useSWR from "swr";
import * as SettingsLayouts from "@/layouts/settings-layouts";
import { Text } from "@opal/components";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { fetchExternalRetrievalSource } from "../../lib";
import { ExternalRetrievalForm } from "../../ExternalRetrievalForm";

const route = ADMIN_ROUTES.EXTERNAL_RETRIEVAL_SOURCES;

export default function Page({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const { data, error, isLoading } = useSWR(
    Number.isFinite(id) ? `/api/external-retrieval/sources/${id}` : null,
    () => fetchExternalRetrievalSource(id)
  );

  return (
    <SettingsLayouts.Root width="full">
      <SettingsLayouts.Header
        icon={route.icon}
        title="Test External Retrieval Source"
        divider
      />
      <SettingsLayouts.Body>
        {isLoading && (
          <div>
            <Text>Loading source...</Text>
          </div>
        )}
        {error && (
          <div className="text-status-danger-05">
            <Text color="inherit">Failed to load source.</Text>
          </div>
        )}
        {data && <ExternalRetrievalForm existingSource={data} testOnly />}
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
