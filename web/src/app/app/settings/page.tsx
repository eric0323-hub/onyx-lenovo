import { redirect } from "next/navigation";
import { isFeatureVisible } from "@/lib/featureVisibility";

export default function SettingsPage() {
  redirect(getDefaultSettingsPath());
}

function getDefaultSettingsPath() {
  if (isFeatureVisible("userSettingsGeneral")) {
    return "/app/settings/general";
  }
  if (isFeatureVisible("userSettingsChatPreferences")) {
    return "/app/settings/chat-preferences";
  }
  if (isFeatureVisible("userSettingsAccountsAccess")) {
    return "/app/settings/accounts-access";
  }
  if (isFeatureVisible("userSettingsConnectors")) {
    return "/app/settings/connectors";
  }

  return "/app";
}
