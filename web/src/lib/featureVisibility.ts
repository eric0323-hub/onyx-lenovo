export type HiddenFeatureFallback = "app" | "404";

export type FeatureVisibilityConfig = {
  /**
   * Master switch. When false, all feature visibility checks are disabled and
   * the application behaves exactly like upstream Onyx.
   */
  enabled: boolean;
  /**
   * What a direct visit to a hidden feature should do.
   * "app" redirects to /app; "404" returns a not-found response in proxy.ts.
   */
  hiddenFeatureFallback: HiddenFeatureFallback;
  /**
   * Base chat workspace at /app. Turn this off only if another route becomes
   * the product's primary screen.
   */
  chat: boolean;
  /**
   * Search mode in the chat header/input, plus search URLs such as
   * /app?searchId=... and /app?allMyDocuments=....
   */
  searchMode: boolean;
  /**
   * Chat history sidebar section and direct chat URLs such as /app?chatId=....
   */
  chatHistory: boolean;
  /**
   * Public/shared chat flows: Share button, /app/shared/[chatId], and
   * /anonymous/[id].
   */
  chatSharing: boolean;
  /**
   * Agent marketplace/editor entry points under /app/agents and agent URLs
   * such as /app?agentId=....
   */
  agents: boolean;
  /**
   * Project sidebar section and project URLs such as /app?projectId=....
   */
  projects: boolean;
  /**
   * User settings shell at /app/settings and the account popover Settings item.
   */
  userSettings: boolean;
  userSettingsGeneral: boolean;
  userSettingsChatPreferences: boolean;
  userSettingsAccountsAccess: boolean;
  userSettingsConnectors: boolean;
  /**
   * Notification center in the account popover.
   */
  notifications: boolean;
  /**
   * File attachment/upload controls in chat/project context.
   */
  fileUploads: boolean;
  /**
   * Agent tool/action picker in the chat input.
   */
  agentActions: boolean;
  /**
   * Deep Research selector in the chat input and the matching submit option.
   */
  deepResearch: boolean;
  /**
   * Multi-model selector and multi-model submission payloads.
   */
  multiModelChat: boolean;
  /**
   * Slash-triggered prompt shortcut picker in the chat input.
   */
  promptShortcuts: boolean;
  /**
   * Speech-to-text microphone control in the chat input.
   */
  voiceInput: boolean;
  /**
   * Read-aloud/TTS controls on assistant messages.
   */
  voicePlayback: boolean;
  /**
   * Like/dislike controls on assistant messages.
   */
  feedbackControls: boolean;
  /**
   * Sources/citation button on assistant messages.
   */
  sourceCitations: boolean;
  /**
   * Self-service sign-up screens and links under /auth/signup.
   */
  authSignup: boolean;
  /**
   * Password reset screens and links under /auth/forgot-password and
   * /auth/reset-password.
   */
  authPasswordReset: boolean;
  /**
   * Join-team flow under /auth/join.
   */
  authJoin: boolean;
  /**
   * Cloud account creation fallback page under /auth/create-account.
   */
  authCreateAccount: boolean;
  /**
   * Email verification screens under /auth/verify-email and
   * /auth/waiting-on-verification.
   */
  authEmailVerification: boolean;
  /**
   * Cloud superuser impersonation screen under /auth/impersonate.
   */
  authImpersonation: boolean;
  /**
   * Admin/curator panel entry point and all /admin routes.
   */
  adminPanel: boolean;
  adminLanguageModels: boolean;
  adminWebSearch: boolean;
  adminImageGeneration: boolean;
  adminVoice: boolean;
  adminCodeInterpreter: boolean;
  adminChatPreferences: boolean;
  adminAgents: boolean;
  adminSkills: boolean;
  adminMcpActions: boolean;
  adminOpenApiActions: boolean;
  adminIndexingStatus: boolean;
  adminAddConnector: boolean;
  adminConnectorDetail: boolean;
  adminDocumentSets: boolean;
  adminDocumentExplorer: boolean;
  adminDocumentFeedback: boolean;
  adminIndexSettings: boolean;
  adminServiceAccounts: boolean;
  adminSlackBots: boolean;
  adminDiscordBots: boolean;
  adminUsers: boolean;
  adminGroups: boolean;
  adminTokenRateLimits: boolean;
  adminObservability: boolean;
  adminUsage: boolean;
  adminQueryHistory: boolean;
  adminCustomAnalytics: boolean;
  adminTheme: boolean;
  adminStandardAnswers: boolean;
  adminBilling: boolean;
  adminHooks: boolean;
  adminScim: boolean;
  adminDebugLogs: boolean;
  adminSecurity: boolean;
  /**
   * LKnow Craft / build mode under /craft.
   */
  craft: boolean;
  /**
   * NRF extension/new-tab routes under /nrf.
   */
  nrf: boolean;
  /**
   * Tool OAuth callback pages that return users to chat after authorizing MCP,
   * federated search, or OpenAPI-backed tools.
   */
  toolOAuthCallbacks: boolean;
};

export const defaultFeatureVisibilityConfig: FeatureVisibilityConfig = {
  enabled: false,
  hiddenFeatureFallback: "app",
  chat: true,
  searchMode: true,
  chatHistory: true,
  chatSharing: true,
  agents: true,
  projects: true,
  userSettings: true,
  userSettingsGeneral: true,
  userSettingsChatPreferences: true,
  userSettingsAccountsAccess: true,
  userSettingsConnectors: true,
  notifications: true,
  fileUploads: true,
  agentActions: true,
  deepResearch: true,
  multiModelChat: true,
  promptShortcuts: true,
  voiceInput: true,
  voicePlayback: true,
  feedbackControls: true,
  sourceCitations: true,
  authSignup: true,
  authPasswordReset: true,
  authJoin: true,
  authCreateAccount: true,
  authEmailVerification: true,
  authImpersonation: true,
  adminPanel: true,
  adminLanguageModels: true,
  adminWebSearch: true,
  adminImageGeneration: true,
  adminVoice: true,
  adminCodeInterpreter: true,
  adminChatPreferences: true,
  adminAgents: true,
  adminSkills: true,
  adminMcpActions: true,
  adminOpenApiActions: true,
  adminIndexingStatus: true,
  adminAddConnector: true,
  adminConnectorDetail: true,
  adminDocumentSets: true,
  adminDocumentExplorer: true,
  adminDocumentFeedback: true,
  adminIndexSettings: true,
  adminServiceAccounts: true,
  adminSlackBots: true,
  adminDiscordBots: true,
  adminUsers: true,
  adminGroups: true,
  adminTokenRateLimits: true,
  adminObservability: true,
  adminUsage: true,
  adminQueryHistory: true,
  adminCustomAnalytics: true,
  adminTheme: true,
  adminStandardAnswers: true,
  adminBilling: true,
  adminHooks: true,
  adminScim: true,
  adminDebugLogs: true,
  adminSecurity: true,
  craft: true,
  nrf: true,
  toolOAuthCallbacks: true,
};

const featureVisibilityConfigKeys = Object.keys(
  defaultFeatureVisibilityConfig
) as (keyof FeatureVisibilityConfig)[];

const featureVisibilityConfigKeySet = new Set<keyof FeatureVisibilityConfig>(
  featureVisibilityConfigKeys
);

function isHiddenFeatureFallback(
  value: unknown
): value is HiddenFeatureFallback {
  return value === "app" || value === "404";
}

function setBooleanFeatureVisibilityOverride(
  overrides: Partial<FeatureVisibilityConfig>,
  key: Exclude<keyof FeatureVisibilityConfig, "hiddenFeatureFallback">,
  value: boolean
): void {
  overrides[key] = value;
}

function parseFeatureVisibilityOverrides(): Partial<FeatureVisibilityConfig> {
  const rawOverrides = process.env.NEXT_PUBLIC_FEATURE_VISIBILITY_OVERRIDES;
  if (!rawOverrides) {
    return {};
  }

  let parsedOverrides: unknown;
  try {
    parsedOverrides = JSON.parse(rawOverrides);
  } catch {
    console.warn(
      "Ignoring NEXT_PUBLIC_FEATURE_VISIBILITY_OVERRIDES because it is not valid JSON."
    );
    return {};
  }

  if (
    parsedOverrides === null ||
    typeof parsedOverrides !== "object" ||
    Array.isArray(parsedOverrides)
  ) {
    console.warn(
      "Ignoring NEXT_PUBLIC_FEATURE_VISIBILITY_OVERRIDES because it must be a JSON object."
    );
    return {};
  }

  const overrides: Partial<FeatureVisibilityConfig> = {};
  for (const [key, value] of Object.entries(parsedOverrides)) {
    const configKey = key as keyof FeatureVisibilityConfig;
    if (!featureVisibilityConfigKeySet.has(configKey)) {
      console.warn(`Ignoring unknown feature visibility override key: ${key}.`);
      continue;
    }

    if (configKey === "hiddenFeatureFallback") {
      if (isHiddenFeatureFallback(value)) {
        overrides.hiddenFeatureFallback = value;
      } else {
        console.warn(
          'Ignoring hiddenFeatureFallback override because it must be "app" or "404".'
        );
      }
      continue;
    }

    if (typeof value === "boolean") {
      setBooleanFeatureVisibilityOverride(overrides, configKey, value);
    } else {
      console.warn(
        `Ignoring feature visibility override "${key}" because it must be a boolean.`
      );
    }
  }

  return overrides;
}

export const featureVisibilityConfig: FeatureVisibilityConfig = {
  ...defaultFeatureVisibilityConfig,
  ...parseFeatureVisibilityOverrides(),
};

export type FeatureVisibilityKey = Exclude<
  keyof FeatureVisibilityConfig,
  "enabled" | "hiddenFeatureFallback"
>;

type PathRule = {
  prefix: string;
  feature: FeatureVisibilityKey;
};

type ExactPathRule = {
  path: string;
  feature: FeatureVisibilityKey;
};

type RouteLike = {
  path: string;
};

const adminRouteFeatureEntries: [string, FeatureVisibilityKey][] = [
  ["/admin/configuration/language-models", "adminLanguageModels"],
  ["/admin/configuration/web-search", "adminWebSearch"],
  ["/admin/configuration/image-generation", "adminImageGeneration"],
  ["/admin/configuration/voice", "adminVoice"],
  ["/admin/configuration/code-interpreter", "adminCodeInterpreter"],
  ["/admin/configuration/chat-preferences", "adminChatPreferences"],
  ["/admin/agents", "adminAgents"],
  ["/admin/skills", "adminSkills"],
  ["/admin/actions/mcp", "adminMcpActions"],
  ["/admin/actions/open-api", "adminOpenApiActions"],
  ["/admin/indexing/status", "adminIndexingStatus"],
  ["/admin/add-connector", "adminAddConnector"],
  ["/admin/documents/sets", "adminDocumentSets"],
  ["/admin/documents/explorer", "adminDocumentExplorer"],
  ["/admin/documents/feedback", "adminDocumentFeedback"],
  ["/admin/configuration/index-settings", "adminIndexSettings"],
  ["/admin/service-accounts", "adminServiceAccounts"],
  ["/admin/bots", "adminSlackBots"],
  ["/admin/discord-bot", "adminDiscordBots"],
  ["/admin/users", "adminUsers"],
  ["/admin/groups", "adminGroups"],
  ["/admin/token-rate-limits", "adminTokenRateLimits"],
  ["/admin/performance/observability", "adminObservability"],
  ["/admin/performance/usage", "adminUsage"],
  ["/admin/performance/query-history", "adminQueryHistory"],
  ["/admin/performance/custom-analytics", "adminCustomAnalytics"],
  ["/admin/theme", "adminTheme"],
  ["/admin/standard-answer", "adminStandardAnswers"],
  ["/admin/billing", "adminBilling"],
  ["/admin/hooks", "adminHooks"],
  ["/admin/scim", "adminScim"],
  ["/admin/debug", "adminDebugLogs"],
  ["/admin/security", "adminSecurity"],
];

const adminRouteFeatureMap = new Map<string, FeatureVisibilityKey>(
  adminRouteFeatureEntries
);

const exactPathRules: ExactPathRule[] = [
  { path: "/app/settings/general", feature: "userSettingsGeneral" },
  {
    path: "/app/settings/chat-preferences",
    feature: "userSettingsChatPreferences",
  },
  {
    path: "/app/settings/accounts-access",
    feature: "userSettingsAccountsAccess",
  },
  { path: "/app/settings/connectors", feature: "userSettingsConnectors" },
  { path: "/federated/oauth/callback", feature: "toolOAuthCallbacks" },
  { path: "/mcp/oauth/callback", feature: "toolOAuthCallbacks" },
  { path: "/oauth-config/callback", feature: "toolOAuthCallbacks" },
  { path: "/auth/signup", feature: "authSignup" },
  { path: "/auth/forgot-password", feature: "authPasswordReset" },
  { path: "/auth/reset-password", feature: "authPasswordReset" },
  { path: "/auth/join", feature: "authJoin" },
  { path: "/auth/create-account", feature: "authCreateAccount" },
  { path: "/auth/verify-email", feature: "authEmailVerification" },
  {
    path: "/auth/waiting-on-verification",
    feature: "authEmailVerification",
  },
  { path: "/auth/impersonate", feature: "authImpersonation" },
];

const pathRules: PathRule[] = [
  { prefix: "/app/agents", feature: "agents" },
  { prefix: "/app/settings", feature: "userSettings" },
  { prefix: "/app/shared", feature: "chatSharing" },
  { prefix: "/anonymous", feature: "chatSharing" },
  { prefix: "/craft", feature: "craft" },
  { prefix: "/nrf", feature: "nrf" },
  { prefix: "/admin/connectors", feature: "adminAddConnector" },
  { prefix: "/admin/connector", feature: "adminConnectorDetail" },
  { prefix: "/admin/actions/edit-mcp", feature: "adminMcpActions" },
  { prefix: "/admin/actions/edit", feature: "adminOpenApiActions" },
  { prefix: "/admin/actions/new", feature: "adminMcpActions" },
  { prefix: "/admin/actions/mcp", feature: "adminMcpActions" },
  { prefix: "/admin/actions/open-api", feature: "adminOpenApiActions" },
  { prefix: "/admin/actions", feature: "adminMcpActions" },
  { prefix: "/admin/groups2", feature: "adminGroups" },
  { prefix: "/admin/federated", feature: "adminIndexingStatus" },
  { prefix: "/admin/systeminfo", feature: "adminDebugLogs" },
  { prefix: "/ee/admin/groups", feature: "adminGroups" },
  { prefix: "/ee/admin/performance/usage", feature: "adminUsage" },
  {
    prefix: "/ee/admin/performance/query-history",
    feature: "adminQueryHistory",
  },
  {
    prefix: "/ee/admin/performance/custom-analytics",
    feature: "adminCustomAnalytics",
  },
  { prefix: "/ee/admin/theme", feature: "adminTheme" },
  { prefix: "/ee/admin/standard-answer", feature: "adminStandardAnswers" },
  { prefix: "/ee/admin/billing", feature: "adminBilling" },
  { prefix: "/ee/agents/stats", feature: "agents" },
];

const appQueryParamRules: { param: string; feature: FeatureVisibilityKey }[] = [
  { param: "chatId", feature: "chatHistory" },
  { param: "searchId", feature: "searchMode" },
  { param: "agentId", feature: "agents" },
  { param: "projectId", feature: "projects" },
  { param: "allMyDocuments", feature: "searchMode" },
];

export function isFeatureVisible(feature: FeatureVisibilityKey): boolean {
  if (!featureVisibilityConfig.enabled) {
    return true;
  }

  if (feature.startsWith("admin") && feature !== "adminPanel") {
    return (
      featureVisibilityConfig.adminPanel === true &&
      featureVisibilityConfig[feature] === true
    );
  }

  if (feature.startsWith("userSettings") && feature !== "userSettings") {
    return (
      featureVisibilityConfig.userSettings === true &&
      featureVisibilityConfig[feature] === true
    );
  }

  return featureVisibilityConfig[feature] === true;
}

export function isAdminRouteVisible(route: RouteLike): boolean {
  const feature = adminRouteFeatureMap.get(route.path);
  return feature ? isFeatureVisible(feature) : true;
}

export function getAdminRouteFeature(
  route: RouteLike
): FeatureVisibilityKey | undefined {
  return adminRouteFeatureMap.get(route.path);
}

export function getFirstVisibleAdminPath(routeEntries: RouteLike[]): string {
  const firstVisibleRoute = routeEntries.find(isAdminRouteVisible);
  return firstVisibleRoute?.path ?? "/app";
}

export function getFeatureForPathname(
  pathname: string
): FeatureVisibilityKey | null {
  const normalizedPathname = normalizePathname(pathname);
  const exactPathRule = exactPathRules.find(
    (rule) => normalizedPathname === rule.path
  );
  if (exactPathRule) {
    return exactPathRule.feature;
  }

  const adminRouteFeature = getFeatureForAdminPathname(normalizedPathname);
  if (adminRouteFeature) {
    return adminRouteFeature;
  }

  const pathRule = pathRules.find((rule) =>
    startsWithPathPrefix(normalizedPathname, rule.prefix)
  );
  if (pathRule) {
    return pathRule.feature;
  }

  if (startsWithPathPrefix(normalizedPathname, "/admin")) {
    return "adminPanel";
  }

  if (normalizedPathname === "/app") {
    return "chat";
  }

  return null;
}

export function getHiddenFeatureForUrl(
  pathname: string,
  searchParams: URLSearchParams
): FeatureVisibilityKey | null {
  if (!featureVisibilityConfig.enabled) {
    return null;
  }

  const pathFeature = getFeatureForPathname(pathname);
  if (pathFeature && !isFeatureVisible(pathFeature)) {
    return pathFeature;
  }

  if (normalizePathname(pathname) === "/app") {
    const queryFeature = appQueryParamRules.find(
      (rule) => searchParams.has(rule.param) && !isFeatureVisible(rule.feature)
    )?.feature;

    if (queryFeature) {
      return queryFeature;
    }
  }

  return null;
}

export function isPathVisible(
  pathname: string,
  searchParams: URLSearchParams = new URLSearchParams()
): boolean {
  return getHiddenFeatureForUrl(pathname, searchParams) === null;
}

function getFeatureForAdminPathname(
  pathname: string
): FeatureVisibilityKey | null {
  for (const [routePath, feature] of adminRouteFeatureMap.entries()) {
    if (startsWithPathPrefix(pathname, routePath)) {
      return feature;
    }
  }

  return null;
}

function startsWithPathPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

function normalizePathname(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1);
  }
  return pathname;
}
