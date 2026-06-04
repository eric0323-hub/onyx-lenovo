# Frontend Feature Visibility

MVP 发布时，前端功能隐藏由 Next.js env 变量控制：`NEXT_PUBLIC_FEATURE_VISIBILITY_OVERRIDES`。为避免多处配置冲突，这个变量统一放在 `web/.env.local` 管理，不再放到 docker compose 的 `.env`、`env.template` 或 compose build args 里。

这个变量是一个 JSON object，用来覆盖 [web/src/lib/featureVisibility.ts](/Users/yangsong/Documents/Lenovo/code/onyx-lenovo/web/src/lib/featureVisibility.ts) 里的默认配置。默认配置是：`enabled: false`，所有功能入口都展示，行为等同上游 Onyx。

注意：`NEXT_PUBLIC_*` 会进入浏览器 bundle，它只适合做“前端展示隐藏 + 前端路由守卫”，不是权限边界。敏感功能仍然需要后端权限或 API 层兜底。Next.js 客户端侧读取这类变量通常发生在构建期；生产环境修改后需要重新构建 web 镜像，开发环境修改后需要重启 Next.js dev server。

## Env 用法

在 `web/.env.local` 中配置：

```env
NEXT_PUBLIC_FEATURE_VISIBILITY_OVERRIDES={"enabled":true,"hiddenFeatureFallback":"app","searchMode":false,"chatHistory":false,"chatSharing":false,"agents":false,"projects":false,"adminPanel":false}
```

变量作用：

| 配置变量                | 作用                                                                                               |
| ----------------------- | -------------------------------------------------------------------------------------------------- |
| `enabled`               | 总开关。`false` 时忽略所有隐藏配置，全部按 Onyx 原逻辑展示；`true` 时启用下方逐项开关。            |
| `hiddenFeatureFallback` | 用户直连隐藏路由时的处理方式。`app` 跳转到 `/app`；`404` 返回 404。                                |
| 其他布尔 key            | 控制对应前端入口是否展示，并控制对应路由或 URL 参数是否放行。`true` 展示/放行，`false` 隐藏/拦截。 |

## User App

| 配置 key                      | 前端展示入口标题                                                                 | 路由 / URL 影响                                                              | 说明                                                                          |
| ----------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `chat`                        | `New Session`、主聊天工作区                                                      | `/app`                                                                       | 主聊天入口。只有当产品首页不再是聊天时才建议关闭。                            |
| `searchMode`                  | 顶部模式按钮 `Search` / `Chat`、输入框占位 `Search connected sources`            | `/app?searchId=...`、`/app?allMyDocuments=...`                               | 控制 Search 模式切换和搜索结果模式。                                          |
| `chatHistory`                 | `Search Chats`、`Recents`、聊天历史条目                                          | `/app?chatId=...`                                                            | 控制侧边栏聊天历史、聊天搜索入口和历史会话直达。                              |
| `chatSharing`                 | `Share`、聊天条目菜单 `Share`                                                    | `/app/shared/[chatId]`、`/anonymous/[id]`                                    | 控制公开/匿名分享聊天相关入口。                                               |
| `agents`                      | `Agents`、`Explore Agents`、`More Agents`、Agent 条目                            | `/app/agents`、`/app?agentId=...`、`/ee/agents/stats`                        | 控制 Agent 市场、Agent 编辑/选择和侧边栏 Agent 区。                           |
| `projects`                    | `Projects`、`New Project`、`Move to Project`、项目条目                           | `/app?projectId=...`                                                         | 控制项目侧边栏、创建项目、移动聊天到项目和项目直达。                          |
| `userSettings`                | 账户菜单 `Settings`、页面标题 `Settings`                                         | `/app/settings`                                                              | 用户设置总入口。关闭后下方用户设置子项都不会显示或放行。                      |
| `userSettingsGeneral`         | 设置左侧 tab `General`                                                           | `/app/settings/general`                                                      | 用户基础设置页。受 `userSettings` 总开关联动。                                |
| `userSettingsChatPreferences` | 设置左侧 tab `Chat Preferences`、`Create New Prompt` 目标页                      | `/app/settings/chat-preferences`                                             | 聊天偏好和 prompt shortcut 管理页。受 `userSettings` 总开关联动。             |
| `userSettingsAccountsAccess`  | 设置左侧 tab `Accounts & Access`                                                 | `/app/settings/accounts-access`                                              | 密码、token、账号访问相关设置。受 `userSettings` 总开关联动。                 |
| `userSettingsConnectors`      | 设置左侧 tab `Connectors`                                                        | `/app/settings/connectors`                                                   | 用户连接器设置。受 `userSettings` 总开关联动。                                |
| `notifications`               | 账户菜单 `Notifications`、通知角标                                               | 无单独页面路由                                                               | 控制通知中心入口和未读角标展示。                                              |
| `fileUploads`                 | 输入框纸夹按钮 tooltip `Attach Files`、附件卡片区域                              | 无单独页面路由                                                               | 控制聊天/项目上下文的上传、粘贴和拖拽文件入口。                               |
| `agentActions`                | 输入框工具/action 选择器                                                         | 无单独页面路由                                                               | 控制 Agent tools/actions 选择入口。                                           |
| `deepResearch`                | 输入框按钮 `Deep Research`                                                       | 无单独页面路由                                                               | 控制 Deep Research 选择和提交参数。                                           |
| `multiModelChat`              | 多模型选择器 / Multi-model 提交                                                  | 无单独页面路由                                                               | 控制多模型聊天入口和 payload。                                                |
| `promptShortcuts`             | 输入 `/` 后的 prompt shortcut 菜单、`Create New Prompt`                          | `/app/settings/chat-preferences` 间接受影响                                  | 控制 slash prompt 快捷菜单。                                                  |
| `voiceInput`                  | 麦克风按钮、`Set up voice` / `Voice not configured...`                           | 无单独页面路由                                                               | 控制语音输入 STT 入口。                                                       |
| `voicePlayback`               | 消息朗读/TTS 按钮、播放波形                                                      | 无单独页面路由                                                               | 控制助手消息朗读和自动播放控制。                                              |
| `feedbackControls`            | 消息 toolbar 的 `Good Response`、`Bad Response`、`Remove Like`、`Remove Dislike` | 无单独页面路由                                                               | 控制助手消息点赞/点踩反馈按钮。                                               |
| `sourceCitations`             | 消息 toolbar 的 `Sources`                                                        | 无单独页面路由                                                               | 控制引用来源按钮和文档侧栏入口。                                              |
| `authSignup`                  | 登录页 `Create an account`、`Create an Account`                                  | `/auth/signup`                                                               | 控制自助注册页和登录页注册链接。                                              |
| `authPasswordReset`           | 登录页 `Reset Password`                                                          | `/auth/forgot-password`、`/auth/reset-password`                              | 控制忘记密码和重置密码入口。还受 `NEXT_PUBLIC_FORGOT_PASSWORD_ENABLED` 影响。 |
| `authJoin`                    | 加入团队流程页面                                                                 | `/auth/join`                                                                 | 控制 join-team 流程。                                                         |
| `authCreateAccount`           | 创建账号兜底页                                                                   | `/auth/create-account`                                                       | 控制云端账号创建兜底页。                                                      |
| `authEmailVerification`       | 邮箱验证 / 等待验证页面                                                          | `/auth/verify-email`、`/auth/waiting-on-verification`                        | 控制邮箱验证相关页面。                                                        |
| `authImpersonation`           | 云端超管 impersonation 页面                                                      | `/auth/impersonate`                                                          | 控制 impersonation 页面。                                                     |
| `craft`                       | 侧边栏 `Craft`、Craft 引导动画                                                   | `/craft`                                                                     | 控制 LKnow Craft / build mode 入口。还受后端/settings 里的 Craft 开关影响。   |
| `nrf`                         | NRF 浏览器扩展 / new-tab 入口                                                    | `/nrf`                                                                       | 控制 NRF 相关前端路由。                                                       |
| `toolOAuthCallbacks`          | 工具授权回调页面                                                                 | `/federated/oauth/callback`、`/mcp/oauth/callback`、`/oauth-config/callback` | 控制 MCP、federated search、OpenAPI 工具 OAuth 回调页面。                     |

## Admin

`adminPanel` 是 Admin/Curator 总入口。它关闭时，所有 `admin...` 子开关即使为 `true` 也不会显示或放行。

| 配置 key                | 前端展示入口标题                           | 路由 / URL 影响                                                                           | 说明                                                       |
| ----------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `adminPanel`            | 侧边栏底部 `Admin Panel` / `Curator Panel` | `/admin/*`                                                                                | Admin/Curator 总入口和全部 admin 路由总开关。              |
| `adminLanguageModels`   | `Language Models`                          | `/admin/configuration/language-models`                                                    | 管理 LLM provider 和模型配置。                             |
| `adminWebSearch`        | `Web Search`                               | `/admin/configuration/web-search`                                                         | 管理 Web Search 配置。                                     |
| `adminImageGeneration`  | `Image Generation`                         | `/admin/configuration/image-generation`                                                   | 管理图片生成配置。                                         |
| `adminVoice`            | `Voice`                                    | `/admin/configuration/voice`                                                              | 管理语音 STT/TTS 配置。                                    |
| `adminCodeInterpreter`  | `Code Interpreter`                         | `/admin/configuration/code-interpreter`                                                   | 管理代码解释器配置。                                       |
| `adminChatPreferences`  | `Chat Preferences`                         | `/admin/configuration/chat-preferences`                                                   | 管理全局聊天偏好。                                         |
| `adminAgents`           | `Agents`                                   | `/admin/agents`                                                                           | 管理 Agent。                                               |
| `adminSkills`           | `Skills`                                   | `/admin/skills`                                                                           | 管理 Skills。                                              |
| `adminMcpActions`       | `MCP Actions`                              | `/admin/actions/mcp`、`/admin/actions`、`/admin/actions/new`、`/admin/actions/edit-mcp/*` | 管理 MCP Actions。默认 `/admin/actions` 归到 MCP Actions。 |
| `adminOpenApiActions`   | `OpenAPI Actions`                          | `/admin/actions/open-api`、`/admin/actions/edit/*`                                        | 管理 OpenAPI Actions。                                     |
| `adminIndexingStatus`   | `Existing Connectors`                      | `/admin/indexing/status`、`/admin/federated/[id]`                                         | 查看连接器索引状态和 federated connector 详情。            |
| `adminAddConnector`     | `Add Connector`                            | `/admin/add-connector`、`/admin/connectors/[connector]`                                   | 添加连接器和连接器类型配置页。                             |
| `adminConnectorDetail`  | 连接器详情页                               | `/admin/connector/[ccPairId]`                                                             | 单个 connector-credential pair 详情页。                    |
| `adminDocumentSets`     | `Document Sets`                            | `/admin/documents/sets`                                                                   | 管理文档集。                                               |
| `adminDocumentExplorer` | `Explorer` / 页面标题 `Document Explorer`  | `/admin/documents/explorer`                                                               | 文档浏览器入口。                                           |
| `adminDocumentFeedback` | `Feedback` / 页面标题 `Document Feedback`  | `/admin/documents/feedback`                                                               | 文档反馈入口。                                             |
| `adminIndexSettings`    | `Index Settings`                           | `/admin/configuration/index-settings`                                                     | 索引配置入口。                                             |
| `adminServiceAccounts`  | `Service Accounts`                         | `/admin/service-accounts`                                                                 | API/service account 管理入口。                             |
| `adminSlackBots`        | `Slack Integration`                        | `/admin/bots`                                                                             | Slack bot 集成入口。                                       |
| `adminDiscordBots`      | `Discord Integration`                      | `/admin/discord-bot`                                                                      | Discord bot 集成入口。                                     |
| `adminUsers`            | `Users` / 页面标题 `Users & Requests`      | `/admin/users`                                                                            | 用户和申请管理入口。                                       |
| `adminGroups`           | `Groups` / 页面标题 `Manage User Groups`   | `/admin/groups`、`/admin/groups2`、`/ee/admin/groups`                                     | 用户组管理入口。                                           |
| `adminTokenRateLimits`  | `Spending Limits`                          | `/admin/token-rate-limits`                                                                | Token/rate limit 配置入口。                                |
| `adminObservability`    | `Observability`                            | `/admin/performance/observability`                                                        | Langfuse/观测入口。                                        |
| `adminUsage`            | `Usage Statistics`                         | `/admin/performance/usage`、`/ee/admin/performance/usage`                                 | 使用量统计入口。                                           |
| `adminQueryHistory`     | `Query History`                            | `/admin/performance/query-history`、`/ee/admin/performance/query-history`                 | 查询历史入口。                                             |
| `adminCustomAnalytics`  | `Custom Analytics`                         | `/admin/performance/custom-analytics`、`/ee/admin/performance/custom-analytics`           | 自定义分析入口。                                           |
| `adminTheme`            | `Appearance & Theming`                     | `/admin/theme`、`/ee/admin/theme`                                                         | 主题和外观配置入口。                                       |
| `adminStandardAnswers`  | `Standard Answers`                         | `/admin/standard-answer`、`/ee/admin/standard-answer`                                     | 标准答案入口。                                             |
| `adminBilling`          | `Plans & Billing`                          | `/admin/billing`、`/ee/admin/billing`                                                     | 计费入口。                                                 |
| `adminHooks`            | `Hook Extensions`                          | `/admin/hooks`                                                                            | Hook 扩展入口。                                            |
| `adminScim`             | `SCIM`                                     | `/admin/scim`                                                                             | SCIM 配置入口。                                            |
| `adminDebugLogs`        | `Debug Logs`                               | `/admin/debug`、`/admin/systeminfo`                                                       | Debug logs 和 system info 入口。                           |
| `adminSecurity`         | `Security and Hardening`                   | `/admin/security`                                                                         | 安全加固入口。                                             |

## 推荐 MVP 示例

下面示例保留主聊天，隐藏搜索、历史、分享、Agent、Projects 和整个 Admin 面板：

```env
NEXT_PUBLIC_FEATURE_VISIBILITY_OVERRIDES={"enabled":true,"hiddenFeatureFallback":"app","searchMode":false,"chatHistory":false,"chatSharing":false,"agents":false,"projects":false,"adminPanel":false}
```

如果只想隐藏某些 Admin 子页面，但仍保留 Admin 入口：

```env
NEXT_PUBLIC_FEATURE_VISIBILITY_OVERRIDES={"enabled":true,"hiddenFeatureFallback":"app","adminPanel":true,"adminBilling":false,"adminUsage":false,"adminQueryHistory":false,"adminCustomAnalytics":false}
```
