# Onyx 前端代码讲解文档

## 1. 文档目标

本文面向第一次阅读或准备二次开发 Onyx 前端的工程人员，目标是把 `web/` 目录中的技术栈、代码分层、页面路由、数据请求、核心业务页面、组件规范和测试方式讲清楚。

Onyx 前端不是一个简单的 Chat UI。它承载了企业知识库产品的主要交互入口，包括聊天、搜索、Agent、项目、文件、连接器管理、模型配置、权限管理、技能、MCP、Craft、语音、Web Search 和企业版管理能力。

推荐阅读方式：

1. 先理解 Next.js App Router 的页面结构。
2. 再理解全局 Provider、API 代理、SWR 数据请求。
3. 然后按业务页面阅读：聊天页、管理后台、Agent、连接器、设置页。
4. 最后理解 Opal 设计系统和组件迁移规范。

## 2. 前端技术栈

Onyx 前端核心位于 `web/`，主要技术栈如下。

| 类型 | 技术/框架 | 作用 |
|---|---|---|
| Web 框架 | Next.js 16 | App Router、页面路由、route handler、构建和服务端能力 |
| UI 框架 | React 19 | 组件、hooks、状态和交互 |
| 类型系统 | TypeScript | 严格类型约束 |
| 样式 | Tailwind CSS 4 + Opal styles | 原子样式和设计系统样式 |
| 设计系统 | `@onyx-ai/opal` | 新 UI 首选组件库 |
| 数据请求 | fetch + SWR | 客户端数据请求、缓存和重试 |
| 状态管理 | React Context + Zustand | 全局状态、聊天状态、sidebar 状态 |
| UI 基础库 | Radix UI、Headless UI、Lucide、Phosphor | 弹窗、菜单、选择器、tooltip、图标等 |
| 动画 | motion | 页面和局部交互动效 |
| 可视化 | Recharts | 图表 |
| 富文本/Markdown | react-markdown、remark、rehype、KaTeX、highlight.js | 聊天消息、代码和数学公式渲染 |
| 监控 | Sentry、PostHog、Web Vitals | 错误、行为和性能观测 |
| 测试 | Jest、Testing Library、Playwright、Storybook | 单测、组件测试、端到端测试、组件预览 |
| 包管理 | Bun | 依赖和脚本执行 |
| Lint/Format | oxlint、oxfmt、tsgo | 静态检查、格式化、类型检查 |

`web/package.json` 中常用脚本：

```bash
bun run dev
bun run build
bun run lint
bun run types:check
bun run format
bun run test
bun run playwright
bun run storybook
```

## 3. 一句话理解前端架构

Onyx 前端可以理解为：

```text
Next.js App Router 页面
  -> Layout 和 Provider 注入全局状态
  -> 页面组件读取 URL / Context / SWR 数据
  -> 业务组件发起 /api/* 请求
  -> 开发环境由 Next route handler 代理到 FastAPI
  -> 后端返回 JSON 或 stream
  -> 前端更新聊天、搜索、管理页面状态
```

核心分层如下：

```text
src/app/              Next.js App Router 页面和 route handlers
src/providers/        全局 Provider，用户、设置、SWR、查询控制等
src/lib/              API service、类型、工具函数、SWR hooks
src/hooks/            业务 hooks 和复用 hooks
src/refresh-pages/    新版页面级业务组件
src/sections/         功能域复合组件
src/layouts/          页面布局组件
src/refresh-components/ 仍在生产使用但未迁移到 Opal 的组件
lib/opal/src/         Opal 设计系统，新增 UI 首选
src/components/       旧组件目录，不建议新增依赖
```

## 4. 顶层目录结构

| 目录/文件 | 作用 |
|---|---|
| `web/src/app` | Next.js App Router 页面、layout、route handler |
| `web/src/providers` | 全局 React Provider |
| `web/src/lib` | API service、业务类型、fetcher、工具函数 |
| `web/src/hooks` | 跨页面复用 hooks |
| `web/src/refresh-pages` | 新版页面级组件 |
| `web/src/refresh-components` | 生产中仍使用、尚未迁移到 Opal 的组件 |
| `web/src/sections` | 业务复合组件，例如 chat、sidebar、cards、input |
| `web/src/layouts` | 页面布局组件，例如 app/admin/settings/sidebar layout |
| `web/src/interfaces` | 部分共享接口定义 |
| `web/src/ee` | 企业版前端扩展 |
| `web/lib/opal/src` | Opal 设计系统源码 |
| `web/tests/e2e` | Playwright 端到端测试 |
| `web/.storybook` | Storybook 配置 |
| `web/next.config.js` | Next.js 构建、重写、重定向、安全头配置 |
| `web/package.json` | 前端依赖和脚本 |

## 5. Next.js App Router

页面入口集中在 `web/src/app`。

常见页面路径：

| 路径 | 文件/目录 | 说明 |
|---|---|---|
| `/` | `src/app/page.tsx` | 根路径入口，通常重定向或进入主应用 |
| `/app` | `src/app/app/page.tsx` | 主聊天/搜索工作台 |
| `/app/agents` | `src/app/app/agents/page.tsx` | 用户侧 Agent 页面 |
| `/app/settings` | `src/app/app/settings/page.tsx` | 用户设置 |
| `/admin/*` | `src/app/admin/*` | 管理后台 |
| `/auth/*` | `src/app/auth/*` | 登录、注册、重置密码、OAuth、SAML |
| `/connector/oauth` | `src/app/connector/oauth` | connector OAuth 回调 |
| `/federated/oauth` | `src/app/federated/oauth` | 联邦连接器 OAuth |
| `/oauth-config/callback` | `src/app/oauth-config/callback/page.tsx` | OAuth config 回调 |
| `/craft` | `src/app/craft` | Craft / AI 工作台 |
| `/mcp/[[...path]]` | `src/app/mcp/[[...path]]/route.ts` | MCP HTTP route |
| `/nrf` | `src/app/nrf` | NRF 相关页面 |
| `/anonymous/[id]` | `src/app/anonymous/[id]/page.tsx` | 匿名共享访问 |

App Router 中的文件类型：

| 文件 | 作用 |
|---|---|
| `layout.tsx` | 页面布局和服务端认证边界 |
| `page.tsx` | 页面入口 |
| `route.ts` | route handler，例如 API 代理或 logout |
| `loading.tsx` | 路由 loading 状态 |

## 6. Root Layout 与全局 Provider

根布局在 `web/src/app/layout.tsx`。

它负责：

1. 引入全局 CSS。
2. 配置 Google font。
3. 设置 metadata。
4. 使用 `dynamic = "force-dynamic"` 避免 build 时静态预渲染触发 cookies 相关问题。
5. 注入主题、tooltip、PostHog、SWR、全局 App Provider。
6. 渲染健康状态 banner、license banner、动态 metadata、analytics、modal root。
7. 根据环境启用 Web Vitals 和 stats overlay。

Provider 层级主要由 `web/src/providers/AppProvider.tsx` 管理：

```text
SettingsProvider
  -> UserProvider
    -> AppBackgroundProvider
      -> ProviderContextProvider
        -> ModalProvider
          -> SidebarStateProvider
            -> QueryControllerProvider
              -> ToastProvider
```

各 Provider 大致职责：

| Provider | 作用 |
|---|---|
| `SettingsProvider` | 应用设置、feature flags、是否启用向量库等 |
| `UserProvider` | 当前用户认证状态和用户信息 |
| `AppBackgroundProvider` | 根据用户偏好设置背景 |
| `ProviderContextProvider` | LLM provider 配置上下文 |
| `ModalProvider` | 全局 modal 状态 |
| `SidebarStateProvider` | sidebar 展开/收起状态 |
| `QueryControllerProvider` | 搜索/聊天模式和 query 生命周期 |
| `ToastProvider` | 全局 toast |
| `SWRConfigProvider` | SWR 全局重试策略 |

这套 Provider 让根布局本身不做复杂数据请求，而是让各 provider 和页面通过 SWR 在客户端获取数据。

## 7. API 代理与前后端通信

开发环境中的核心 API 代理文件是：

```text
web/src/app/api/[...path]/route.ts
```

它会接收前端对 `/api/*` 的请求，然后转发到 `INTERNAL_URL` 指向的 FastAPI 后端。

流程：

```text
浏览器请求 /api/chat/send-message
  -> Next.js route handler
  -> 拼接 INTERNAL_URL/chat/send-message
  -> 转发 method、headers、body、query params
  -> 保留 set-cookie
  -> 如果是 stream，则透传 stream
  -> 返回给浏览器
```

需要注意：

- 该代理默认只在 `NODE_ENV=development` 下可用。
- 生产环境预期由 nginx 或其他反向代理处理 `/api/*`。
- 可以通过 `OVERRIDE_API_PRODUCTION=true` 给 preview 环境放开。
- 开发调试远程后端时，可以用 `DEBUG_AUTH_COOKIE` 注入 auth cookie。
- 对于流式响应，route handler 会用 `TransformStream` 透传。

项目中后端调用建议走：

```text
http://localhost:3000/api/...
```

而不是直接请求：

```text
http://localhost:8080/...
```

这样更贴近真实前后端路径，也能覆盖 cookie、代理和 stream 行为。

## 8. `next.config.js`

`web/next.config.js` 负责构建、运行时、安全头、重写和重定向。

关键配置：

| 配置 | 作用 |
|---|---|
| `output: "standalone"` | 生产构建输出 standalone |
| `transpilePackages: ["@onyx-ai/opal"]` | 转译 workspace 内的 Opal 包 |
| `typedRoutes: true` | 启用 Next typed routes |
| `reactCompiler: true` | 启用 React Compiler |
| `turbopack.root = __dirname` | 固定 Turbopack root 到 `web/` |
| `images.unoptimized = true` | 禁用 Next image optimization |
| `headers()` | CSP、HSTS、Referrer Policy、Permissions Policy 等 |
| `rewrites()` | PostHog、API docs、OpenAPI 转发 |
| `redirects()` | `/chat` 到 `/app`、assistants 到 agents 等历史路径迁移 |

安全头里 CSP 允许自身、Google Fonts，并禁用 object、限制 form action。Permissions Policy 默认关闭大多数敏感浏览器能力，只允许 self microphone。

## 9. 数据请求与 Service 层

前端主要使用 `fetch` 和 SWR。

通用 fetcher 在：

```text
web/src/lib/fetcher.ts
```

它定义了：

- `FetchError`
- `RedirectError`
- `errorHandlingFetcher<T>()`
- `skipRetryOnAuthError`

`skipRetryOnAuthError` 会阻止 SWR 对 401、402、403 自动重试，避免未登录或权限不足页面反复打后端。

业务 service 常放在 `web/src/lib/<domain>/svc.ts` 或页面目录自己的 `svc.ts`。

例子：

| 目录/文件 | 作用 |
|---|---|
| `src/lib/chat/svc.ts` | 聊天文件、聊天相关请求 |
| `src/lib/agents/svc.ts` | Agent 请求 |
| `src/lib/languageModels/svc.ts` | 模型 provider 请求 |
| `src/lib/indexing/svc.ts` | 索引状态请求 |
| `src/lib/webSearch/svc.ts` | Web Search 配置请求 |
| `src/lib/voice/svc.ts` | 语音能力请求 |
| `src/refresh-pages/admin/*/svc.ts` | 管理页面局部 service |

常见数据流：

```text
组件或 hook
  -> useSWR(key, fetcher)
  -> src/lib 或页面 svc
  -> /api/* 代理
  -> FastAPI
  -> 返回 JSON
  -> SWR 缓存和重新渲染
```

## 10. 主应用布局与认证边界

主应用布局在：

```text
web/src/app/app/layout.tsx
```

它是服务端组件，会调用 `requireAuth()` 做认证检查。未登录时通过 `redirect()` 跳转。

认证通过后，它注入：

- `ProjectsProvider`
- `VoiceModeProvider`
- `AppSidebar`
- 页面 children

布局结构大致是：

```text
ProjectsProvider
  -> VoiceModeProvider
    -> flex row
      -> AppSidebar
      -> page content
```

管理后台布局在：

```text
web/src/app/admin/layout.tsx
web/src/layouts/admin/Layout.tsx
```

管理后台通常会有更严格的权限判断和统一 admin layout。

## 11. 聊天/搜索主页面

主页面入口：

```text
web/src/app/app/page.tsx
```

它很薄，只读取 `searchParams.firstMessage`，然后渲染：

```text
web/src/refresh-pages/AppPage.tsx
```

`AppPage` 是主聊天/搜索工作台的核心页面组件。它是 client component，负责整合大量状态：

- 当前用户。
- settings。
- chat sessions。
- 当前 chat session。
- agents。
- document sets。
- cc pairs。
- tags。
- federated connectors。
- projects。
- 当前上传文件。
- 当前 agent。
- deep research 开关。
- sidebar 状态。
- search params。
- chat controller。
- multi model chat controller。
- document sidebar。

主页面里几个关键模块：

| 模块 | 作用 |
|---|---|
| `AppInputBar` | 输入框、上传文件、提交消息 |
| `ChatUI` | 聊天消息展示 |
| `ChatScrollContainer` | 聊天滚动容器 |
| `DocumentsSidebar` | 文档/引用侧边栏 |
| `AppSidebar` | 左侧导航和会话列表 |
| `ProjectContextPanel` | 项目上下文 |
| `ModelSelector` | 模型选择 |
| `NoAgentModal` | 无可用 Agent 提示 |
| `FederatedOAuthModal` | 联邦连接器授权 |
| `PreviewModal` | 文档预览 |
| `SearchUI` | 搜索模式 UI，企业版可替换 |

主聊天页的数据流可以理解为：

```text
用户输入
  -> AppInputBar
  -> useChatController / useMultiModelChat
  -> /api/chat/* stream
  -> 解析后端 packet
  -> 更新 useChatSessionStore
  -> ChatUI 渲染消息和引用
```

## 12. 聊天状态管理

聊天相关状态主要分布在：

```text
web/src/hooks/useChatController.ts
web/src/hooks/useMultiModelChat.ts
web/src/hooks/useChatSessionController.ts
web/src/hooks/useChatSessions.ts
web/src/app/app/stores/useChatSessionStore.ts
```

大致职责：

| 模块 | 作用 |
|---|---|
| `useChatSessions` | 会话列表、当前会话加载和刷新 |
| `useChatController` | 单次聊天提交、停止、状态控制 |
| `useMultiModelChat` | 多模型聊天逻辑 |
| `useChatSessionController` | 会话选择、切换、更新 |
| `useChatSessionStore` | 当前消息树、当前聊天状态、stream 状态、文档侧栏状态 |

后端聊天接口返回的是流式 packet，前端需要边接收边更新 UI。这也是为什么聊天页大量状态在 client component 和 Zustand store 中。

## 13. 管理后台页面

管理后台路径集中在：

```text
web/src/app/admin
web/src/refresh-pages/admin
web/src/sections/admin
```

常见页面：

| 路径 | 页面职责 |
|---|---|
| `/admin/users` | 用户管理 |
| `/admin/groups` | 用户组管理 |
| `/admin/agents` | 管理 Agent |
| `/admin/skills` | 管理 Skills |
| `/admin/connectors` | 数据源连接器列表 |
| `/admin/add-connector` | 新增连接器 |
| `/admin/indexing` | 索引状态 |
| `/admin/security` | 安全配置 |
| `/admin/token-rate-limits` | Token 限流 |
| `/admin/systeminfo` | 系统信息 |
| `/admin/bots` / `/admin/discord-bot` | Bot 配置 |
| `/admin/actions` | Actions 管理 |
| `/admin/hooks` | Hooks 管理 |
| `/admin/service-accounts` | 服务账号/API Key |
| `/admin/billing` | 计费 |

新版管理页面多放在 `src/refresh-pages/admin/*`，页面内部常见组织方式：

```text
index.tsx        页面主组件
svc.ts           API 请求封装
interfaces.ts    类型定义
shared.tsx       页面内共享 UI
Modal.tsx        页面相关 modal
Table.tsx        页面相关表格
```

## 14. 连接器与知识库配置前端

连接器相关代码主要在：

```text
web/src/app/admin/add-connector
web/src/app/admin/connectors
web/src/components/admin/connectors
web/src/lib/connectors
web/src/lib/connector.ts
web/src/lib/credential.ts
web/src/lib/ccPair.ts
```

前端连接器页面通常负责：

1. 展示支持的数据源。
2. 渲染不同 connector 的配置表单。
3. 管理凭据。
4. 处理 OAuth 授权。
5. 创建 connector / credential / cc pair。
6. 展示同步状态和错误。

后端真正执行抓取和索引，前端负责配置、状态展示和用户操作入口。

## 15. Agent、Tool、Skill 与 MCP 前端

相关目录：

```text
web/src/lib/agents
web/src/lib/tools
web/src/lib/skills
web/src/app/app/agents
web/src/app/admin/agents
web/src/app/admin/skills
web/src/app/mcp
web/src/sections/agents
```

概念对应关系：

| 概念 | 前端职责 |
|---|---|
| Agent / Persona | 创建、编辑、选择、展示、权限和知识范围配置 |
| Tool | 配置 Agent 可用工具，处理 OAuth 状态，展示工具信息 |
| Skill | 上传、分享、内置/自定义 skill 列表 |
| MCP | MCP server 配置、OAuth、工具发现和管理 |

用户侧通常关心“选择哪个 Agent 完成工作”，管理员侧关心“哪些 Agent、Tools、Skills 可以被谁使用”。

## 16. Craft 与项目能力

Craft 相关目录：

```text
web/src/app/craft
web/src/lib/build
```

项目上下文相关目录：

```text
web/src/app/app/projects
web/src/app/app/components/projects
web/src/providers/ProjectsContext
```

Craft 是偏 AI 工作台/产物生成的能力，和 sandbox、code interpreter、artifact、scheduled task 等后端能力相关。

Projects 则把聊天、文件、上下文和会话组织在一起，让用户可以在一个项目中持续工作。

## 17. Opal 设计系统与组件规范

前端正在向 Opal 设计系统迁移。规范写在 `web/AGENTS.md`，这是前端开发的单一事实来源。

组件优先级：

```text
1. web/lib/opal/src/           新 UI 首选
2. web/src/refresh-components/ 生产组件，尚未迁移到 Opal
3. web/src/sections/           业务复合组件
4. web/src/layouts/            页面布局组件
5. web/src/components/         旧组件，不要新增依赖
```

关键规则：

- 新组件优先用 Opal。
- 不要新增使用 `web/src/components/` 中的 legacy 组件。
- 按钮使用 Opal `Button`，不要直接写裸 `<button>`。
- icon + title + description 组合使用 `Content`。
- 带右侧操作的内容块使用 `ContentAction`。
- 空状态、错误页、提示页使用 `IllustrationContent`。
- admin/settings 页面使用 `src/layouts/settings-layouts.tsx`。
- 信息卡片类组件放到 `web/src/sections/cards/`。

Opal 常见目录：

| 目录 | 作用 |
|---|---|
| `components/buttons` | Button |
| `components/cards` | Card |
| `components/inputs` | 输入组件 |
| `components/table` | 表格 |
| `components/tabs` | Tabs |
| `components/tooltip` | Tooltip |
| `core/interactive` | 交互状态底层 |
| `layouts/content` | Content |
| `layouts/content-action` | ContentAction |
| `layouts/illustration-content` | IllustrationContent |
| `icons` | 图标 |
| `illustrations` | 插画 |

## 18. 布局体系

前端有多个 layout 层级。

| 目录/文件 | 作用 |
|---|---|
| `src/app/layout.tsx` | 全站 root layout |
| `src/app/app/layout.tsx` | 主应用认证和 sidebar 布局 |
| `src/app/admin/layout.tsx` | 管理后台布局入口 |
| `src/layouts/admin/Layout.tsx` | 管理后台实际布局 |
| `src/layouts/settings-layouts.tsx` | 设置页标准布局 |
| `src/layouts/sidebar-layouts` | Sidebar 状态和布局 |
| `src/layouts/app-layouts` | 主应用页面布局 |
| `src/layouts/general-layouts` | 通用布局 primitive |

做新页面时，先判断它属于：

- 主应用 `/app`。
- 管理后台 `/admin`。
- 认证 `/auth`。
- Craft `/craft`。
- 独立 route handler。

然后复用对应 layout，而不是在页面里重新搭一套框架。

## 19. 企业版前端扩展

企业版前端代码主要在：

```text
web/src/ee
web/src/app/ee
```

常见用途：

- 企业版 admin 页面。
- 企业搜索增强。
- 付费 tier gating。
- 企业 hooks / providers。
- CE/EE 组件替换。

代码中可以看到类似：

```typescript
import { paidTierGated } from "@/ce";
import EESearchUI from "@/ee/sections/SearchUI";
const SearchUI = paidTierGated(EESearchUI);
```

这类模式用于在不同版本/权限下选择展示 CE 或 EE 能力。

## 20. 类型与生成代码

类型定义散布在几个地方：

| 位置 | 说明 |
|---|---|
| `src/lib/types.ts` | 常用共享类型 |
| `src/lib/search/interfaces.ts` | 搜索相关类型 |
| `src/lib/agents/types.ts` | Agent 类型 |
| `src/lib/tools/interfaces.ts` | Tool 类型 |
| `src/lib/languageModels/types.ts` | 模型配置类型 |
| `src/interfaces` | 跨模块接口 |
| `src/lib/generated` | 生成代码 |

项目要求 TypeScript 严格类型。新增 service、hook、组件 props 时应明确类型，避免 `any` 扩散。

## 21. 测试与质量检查

常用命令：

```bash
cd web
bun run lint
bun run types:check
bun run format:check
bun run test
bun run playwright
```

测试类型：

| 类型 | 位置/命令 | 说明 |
|---|---|---|
| Jest 单测 | `bun run test` | 工具函数、hooks、部分组件 |
| Testing Library | 与 Jest 配合 | 组件行为测试 |
| Playwright E2E | `web/tests/e2e`，`bunx playwright test` | 完整前后端链路 |
| Storybook | `bun run storybook` | 组件开发和视觉预览 |
| Type Check | `bun run types:check` | TypeScript 类型检查 |
| Lint | `bun run lint` | oxlint |
| Format | `bun run format` / `format:check` | oxfmt |

如果测试需要真实前后端服务，通常可以访问：

```text
http://localhost:3000
```

常用测试登录账号：

```text
username: a@example.com
password: a
```

## 22. 新人读代码建议

### 22.1 想看页面路由

从这里开始：

```text
web/src/app
web/src/app/layout.tsx
web/src/app/app/layout.tsx
web/src/app/app/page.tsx
web/src/app/admin/layout.tsx
```

先理解 App Router，再顺着 `page.tsx` 找到真正的页面组件。

### 22.2 想看主聊天页

从这里开始：

```text
web/src/app/app/page.tsx
web/src/refresh-pages/AppPage.tsx
web/src/sections/input/AppInputBar
web/src/sections/chat/ChatUI.tsx
web/src/hooks/useChatController.ts
web/src/hooks/useMultiModelChat.ts
web/src/app/app/stores/useChatSessionStore.ts
```

### 22.3 想看 API 请求

从这里开始：

```text
web/src/app/api/[...path]/route.ts
web/src/lib/fetcher.ts
web/src/lib/*/svc.ts
web/src/lib/hooks.ts
web/src/hooks
```

注意开发环境下 `/api/*` 会先进入 Next route handler，再代理到后端。

### 22.4 想看管理后台

从这里开始：

```text
web/src/app/admin
web/src/layouts/admin/Layout.tsx
web/src/refresh-pages/admin
web/src/sections/admin
```

新版页面优先看 `refresh-pages/admin`。

### 22.5 想看组件规范

从这里开始：

```text
web/AGENTS.md
web/lib/opal/src
web/src/refresh-components
web/src/sections
web/src/layouts
```

新 UI 首选 Opal，不要新增依赖 `web/src/components`。

### 22.6 想看 Agent / Tool / Skill

从这里开始：

```text
web/src/lib/agents
web/src/lib/tools
web/src/lib/skills
web/src/app/app/agents
web/src/app/admin/agents
web/src/app/admin/skills
web/src/sections/agents
```

### 22.7 想看连接器配置

从这里开始：

```text
web/src/app/admin/add-connector
web/src/app/admin/connectors
web/src/lib/connectors
web/src/lib/connector.ts
web/src/lib/credential.ts
web/src/lib/ccPair.ts
```

## 23. 前端目录速查表

| 目录 | 简要说明 |
|---|---|
| `web/src/app` | App Router 页面和 route handlers |
| `web/src/app/api/[...path]` | 开发环境 API 代理 |
| `web/src/providers` | 全局 providers |
| `web/src/lib` | service、fetcher、类型、工具函数 |
| `web/src/hooks` | 复用 hooks |
| `web/src/refresh-pages` | 新版页面组件 |
| `web/src/refresh-components` | 未迁移到 Opal 的生产组件 |
| `web/src/sections` | 业务复合组件 |
| `web/src/layouts` | 布局组件 |
| `web/src/ee` | 企业版前端扩展 |
| `web/src/components` | 旧组件目录，不建议新增依赖 |
| `web/lib/opal/src` | Opal 设计系统 |
| `web/tests/e2e` | Playwright E2E |
| `web/.storybook` | Storybook |
| `web/next.config.js` | Next 配置 |
| `web/package.json` | 脚本和依赖 |

## 24. 总结

Onyx 前端的主线可以概括为：

```text
页面路由：
src/app -> layout/page -> refresh-pages 或 sections
```

```text
数据请求：
组件/hook -> src/lib service -> /api/* -> Next 代理 -> FastAPI
```

```text
聊天交互：
AppPage -> AppInputBar/useChatController -> stream packet
       -> useChatSessionStore -> ChatUI/DocumentsSidebar
```

```text
组件体系：
Opal 优先 -> refresh-components 兜底 -> sections 组织业务复合组件
```

如果要做二次开发，先判断改动属于哪一层：

- 新页面：看 `src/app`、`refresh-pages`、`layouts`。
- 新 UI 组件：优先放 Opal 或 `sections`。
- 新 API 调用：放 `src/lib/<domain>/svc.ts` 或对应 hook。
- 改聊天体验：看 `AppPage`、chat hooks、chat store、`sections/chat`。
- 改管理后台：看 `src/app/admin` 和 `refresh-pages/admin`。
- 改连接器配置：看 `lib/connectors` 和 admin connector 页面。
- 改企业版能力：看 `src/ee` 和 `src/app/ee`。

掌握这些入口后，再回到具体业务组件会清晰很多。
