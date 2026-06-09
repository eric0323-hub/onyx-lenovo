"use client";

import * as SettingsLayouts from "@/layouts/settings-layouts";
import { ADMIN_ROUTES } from "@/lib/admin-routes";
import { ExternalRetrievalForm } from "../ExternalRetrievalForm";

const route = ADMIN_ROUTES.EXTERNAL_RETRIEVAL_SOURCES;

export default function Page() {
  return (
    <SettingsLayouts.Root width="full">
      <SettingsLayouts.Header
        icon={route.icon}
        title="New External Retrieval Source"
        divider
      />
      <SettingsLayouts.Body>
        <ExternalRetrievalForm />
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
