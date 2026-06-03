# Onyx 后端代码讲解文档

## 1. 文档目标

本文面向第一次阅读或准备二次开发 Onyx 后端的工程人员，目标是把 `backend/` 目录中的框架选型、代码分层、核心业务对象、主要业务链路和各子目录职责讲清楚。

阅读本文时可以把 Onyx 后端理解成一个企业 AI 知识库平台的服务端。它不是单纯的聊天接口，也不是普通 CRUD 后台，而是把企业知识接入、文档索引、权限同步、搜索召回、RAG 问答、Agent 工具调用、模型配置、后台任务和企业治理组合在一起的系统。

推荐阅读顺序：

1. 先理解技术栈和运行时组件。
2. 再理解 `server`、`db`、`connectors`、`indexing`、`document_index`、`chat`、`llm` 这些核心层。
3. 最后顺着“文档索引链路”和“聊天问答链路”两条主业务线回到代码。

相关全局架构图可参考 `docs/architecture/onyx-architecture-zh.md`。本文更聚焦后端代码阅读。

## 2. 后端使用的框架与基础设施

Onyx 后端核心位于 `backend/onyx`，主要技术栈如下。

| 类型 | 技术/框架 | 作用 |
|---|---|---|
| Web API | FastAPI | 提供 HTTP API、依赖注入、路由、中间件、流式响应 |
| 数据校验 | Pydantic | 请求、响应、内部数据模型校验 |
| ORM | SQLAlchemy | PostgreSQL ORM 模型与数据库访问 |
| 数据迁移 | Alembic | 管理数据库 schema 变更 |
| 后台任务 | Celery | 文档抓取、索引、权限同步、清理、监控等异步任务 |
| 队列/缓存/锁 | Redis | Celery broker、分布式锁、缓存、停止信号、任务协调 |
| 关系数据库 | PostgreSQL | 用户、会话、文档元数据、连接器、权限、配置等业务状态 |
| 搜索/向量库 | Vespa / OpenSearch | 文档 chunk 检索、向量搜索、关键词搜索、权限过滤 |
| LLM 网关 | LiteLLM + provider SDK | 统一调用 OpenAI、Anthropic、Gemini、Ollama、自托管模型等 |
| 模型服务 | `backend/model_server` | embedding、rerank、intent 等本地模型推理 |
| 观测 | Sentry / Prometheus / tracing | 错误上报、指标、LLM 调用追踪 |

后端入口文件是 `backend/onyx/main.py`。它创建 FastAPI 应用，注册路由、中间件、异常处理、数据库连接池、metrics、tracing 和启动初始化逻辑。

## 3. 一句话理解后端架构

Onyx 后端可以拆成两条主业务线：

```text
企业知识接入与索引
外部系统 -> connector -> Celery docfetching -> Celery docprocessing
        -> PostgreSQL 元数据 -> chunk / embedding -> Vespa 或 OpenSearch
```

```text
聊天与搜索问答
前端请求 -> FastAPI router -> 权限/会话/Persona/工具配置
        -> 检索相关文档 -> 组装 prompt -> 调用 LLM
        -> 流式返回答案 -> 保存消息、引用、反馈
```

所以读代码时，不要只按文件名看。更有效的方式是按层理解：

```text
server/          API 接入层
db/              数据库模型与数据访问层
connectors/      外部知识源适配层
background/      异步任务调度层
indexing/        文档处理与索引流水线
document_index/  搜索引擎/向量库抽象层
chat/            RAG 聊天编排层
llm/             大模型调用抽象层
tools/           Agent 工具系统
auth/access/     身份认证与权限控制
```

## 4. FastAPI 应用入口

入口文件：`backend/onyx/main.py`

核心函数：

- `get_application()`：创建 FastAPI app，注册业务 router。
- `lifespan()`：应用启动和关闭时执行初始化/释放逻辑。
- `include_router_with_global_prefix_prepended()`：统一给路由加全局 API prefix。
- `register_onyx_exception_handlers()`：注册 Onyx 统一错误处理。

启动时主要做这些事情：

1. 校验配置，例如 `DISABLE_VECTOR_DB` 是否和多租户、Craft 等能力冲突。
2. 初始化 PostgreSQL sync、async、readonly 连接池。
3. 注册 Prometheus 连接池 metrics。
4. 校验认证配置。
5. 初始化 tracing。
6. 预热数据库连接。
7. 单租户模式下执行 `setup_onyx` 和 file store 初始化。
8. 多租户模式下执行 `setup_multitenant_onyx`。
9. 按配置启动认证限流或无向量数据库模式的 periodic poller。

FastAPI app 注册了大量 router，例如：

| Router | 大致职责 |
|---|---|
| `chat_router` | 聊天会话、消息发送、流式回答、停止生成、反馈 |
| `query_router` | 搜索查询 |
| `connector_router` | 数据源连接器管理 |
| `credential_router` | 外部系统凭据管理 |
| `cc_pair_router` | connector 与 credential 的绑定管理 |
| `document_router` | 文档管理 |
| `persona_router` | Assistant / Agent 配置 |
| `tool_router` | Agent 工具配置 |
| `mcp_router` | MCP 服务配置 |
| `skill_router` | Skill 管理 |
| `llm_router` | LLM provider 配置 |
| `embedding_router` | embedding 配置 |
| `settings_router` | 系统设置 |
| `onyx_api_router` | 对外 ingestion API |

新建 API 时项目规范要求不要使用 FastAPI 的 `response_model` 参数，而是直接给函数返回值做类型标注。

## 5. 核心目录总览

### 5.1 `backend/onyx/server`

`server` 是 API 层，放 FastAPI router、请求/响应模型和接口相关辅助逻辑。

典型结构：

| 子目录/文件 | 作用 |
|---|---|
| `query_and_chat/` | 聊天、搜索、流式响应、会话读取 |
| `documents/` | connector、credential、document、targeted reindex |
| `features/` | persona、tool、skill、project、notification、MCP 等产品功能 |
| `manage/` | 管理后台接口，例如用户、LLM、embedding、Slack bot、voice |
| `settings/` | 系统设置接口 |
| `metrics/` | Prometheus 指标 |
| `middleware/` | 请求耗时、认证限流等中间件 |
| `onyx_api/` | 对外 ingestion API |
| `federated/` | 联邦搜索接口 |
| `kg/` | 知识图谱接口 |

这一层一般不直接承担复杂业务算法，而是：

1. 接收请求。
2. 通过 FastAPI dependency 做认证和权限检查。
3. 调用 `db`、`chat`、`indexing`、`llm`、`tools` 等模块。
4. 返回 JSON 或 StreamingResponse。

### 5.2 `backend/onyx/db`

`db` 是数据库层，既包含 SQLAlchemy ORM model，也包含各业务对象的数据访问函数。

核心文件：

| 文件 | 作用 |
|---|---|
| `models.py` | SQLAlchemy ORM 主模型定义 |
| `engine/` | SQLAlchemy engine/session/tenant 管理 |
| `chat.py` | 聊天会话和消息读写 |
| `document.py` / `chunk.py` | 文档和 chunk 数据 |
| `connector.py` | connector 配置 |
| `connector_credential_pair.py` | connector 与 credential 绑定 |
| `credentials.py` | 凭据存储与加密字段 |
| `persona.py` | Assistant / Agent 配置 |
| `llm.py` | LLM provider 配置 |
| `search_settings.py` | 搜索和 embedding 配置 |
| `users.py` / `auth.py` | 用户与认证 |
| `permissions.py` / `document_access.py` | 权限相关数据 |
| `index_attempt.py` | 索引尝试状态 |
| `user_file.py` | 用户上传文件 |

重要特点：

- 敏感字段使用加密类型，例如 `EncryptedString`、`EncryptedJson`。
- 多租户上下文通过 `shared_configs.contextvars` 和 `db/engine` 管理。
- 项目要求所有数据库操作放在 `backend/onyx/db` 或 `backend/ee/onyx/db` 下，避免业务层到处散落 SQL。

### 5.3 `backend/onyx/connectors`

`connectors` 是外部数据源适配层。每个子目录通常对应一种外部系统。

常见连接器：

- `google_drive`
- `slack`
- `confluence`
- `jira`
- `github`
- `gitlab`
- `notion`
- `zendesk`
- `salesforce`
- `sharepoint`
- `gmail`
- `web`
- `file`

连接器的核心职责是把外部系统的数据统一转换成 Onyx 内部的 `Document` 结构，而不是直接写数据库或索引。

常见输入模式：

| 类型 | 含义 |
|---|---|
| `LOAD_STATE` | 加载某个完整状态或保存状态 |
| `POLL` | 按时间范围增量拉取 |
| `EVENT` | 基于外部事件触发 |
| `SLIM_RETRIEVAL` | 只拉取轻量 ID 信息，用于判断删除/过期 |

连接器一般会处理：

1. 加载配置。
2. 加载凭据。
3. 调用外部 API。
4. 分页、checkpoint、增量同步。
5. 构造统一 `Document`、`Section`、metadata、权限信息。
6. 把结果交给后台索引任务。

### 5.4 `backend/onyx/background`

`background` 是后台任务层，重点是 Celery。

核心目录：

| 子目录 | 作用 |
|---|---|
| `celery/apps/` | 不同 Celery app 定义 |
| `celery/configs/` | 不同 worker 配置 |
| `celery/tasks/` | 具体任务函数 |
| `celery/versioned_apps/` | CE/EE 或版本化 app 入口 |
| `indexing/` | 索引任务辅助逻辑、checkpoint、attempt 清理 |

主要 worker 类型：

| Worker | 职责 |
|---|---|
| Primary | 扫描和派发核心任务 |
| Beat | 定时调度 |
| Docfetching | 从外部系统抓取文档 |
| Docprocessing | 文档入库、切块、embedding、写索引 |
| Light | 轻量同步、删除、metadata、checkpoint 清理 |
| Heavy | pruning、权限同步、外部 group sync、CSV、sandbox |
| Monitoring | 健康检查和指标 |
| User File Processing | 用户上传文件处理 |

项目规范要求：

- Celery task 使用 `@shared_task`。
- task 放在 `background/celery/tasks/` 或 `ee/background/celery/tasks/`。
- 发送 task 时必须带 `expires=`，避免任务队列无限增长。
- Celery worker 使用线程池，Celery time limit 在这里不可靠，超时逻辑要在任务内部实现。

### 5.5 `backend/onyx/indexing`

`indexing` 是文档处理与索引流水线。

核心文件：

| 文件 | 作用 |
|---|---|
| `indexing_pipeline.py` | 索引主流程 |
| `chunker.py` | 文档切块入口 |
| `chunking/` | 文本、图片、表格等 section chunker |
| `embedder.py` | embedding 生成 |
| `vector_db_insertion.py` | 写入向量库 |
| `adapters/` | 不同输入到索引模型的适配器 |
| `persistent_indexing.py` | 索引失败记录和恢复 |
| `chunk_batch_store.py` | chunk 批次暂存 |

索引主流程大致是：

```text
Document
  -> 写入/更新 PostgreSQL 文档元数据
  -> 处理 tags、metadata、权限、hierarchy
  -> ingestion hook
  -> chunking
  -> 可选图片总结、chunk summary、contextual RAG
  -> embedding
  -> 写入 Vespa/OpenSearch
  -> 记录 IndexAttempt 状态和 metrics
```

这层是连接器和搜索引擎之间的核心加工环节。

### 5.6 `backend/onyx/document_index`

`document_index` 是搜索引擎/向量数据库抽象层。

核心目录：

| 子目录/文件 | 作用 |
|---|---|
| `interfaces_new.py` | 文档索引统一接口 |
| `factory.py` | 根据配置创建 document index |
| `vespa/` | Vespa 写入、查询、删除、request builder |
| `opensearch/` | OpenSearch client、schema、search |
| `disabled.py` | 禁用向量库模式 |

`indexing` 负责“加工文档”，`document_index` 负责“如何把加工结果写入和查出来”。

典型调用关系：

```text
indexing_pipeline
  -> document_index.factory
  -> VespaDocumentIndex 或 OpenSearchDocumentIndex
```

聊天或搜索时也会通过这里召回相关 chunk。

### 5.7 `backend/onyx/chat`

`chat` 是聊天业务编排层。

核心文件：

| 文件 | 作用 |
|---|---|
| `process_message.py` | 处理用户一轮消息 |
| `llm_loop.py` | 多步 LLM 推理和工具调用循环 |
| `llm_step.py` | 单次 LLM 调用 |
| `chat_utils.py` | 会话、历史、上下文辅助 |
| `prompt_utils.py` | prompt 组装 |
| `citation_processor.py` | 引用处理 |
| `save_chat.py` | 消息保存 |
| `emitter.py` | 流式 packet 输出 |
| `chat_state.py` | 聊天状态容器 |
| `compression.py` | 上下文压缩 |

聊天 API 在 `server/query_and_chat/chat_backend.py`，但真正的复杂逻辑主要在 `chat/`。

聊天一轮请求大概会做：

1. 校验用户和权限。
2. 加载 chat session 和历史消息。
3. 加载 Persona/Agent 配置。
4. 加载可用工具、文件、项目上下文。
5. 检查 token 限额和模型可用性。
6. 构造 prompt、system message、历史上下文。
7. 进入 LLM loop。
8. 按需调用工具，例如搜索、Web Search、文件读取、代码执行、MCP。
9. 生成最终回答。
10. 流式返回 packet。
11. 保存消息、引用、工具调用和反馈相关状态。

### 5.8 `backend/onyx/llm`

`llm` 是大模型抽象层。

主要职责：

- 根据配置构造 LLM provider。
- 统一 OpenAI、Anthropic、Gemini、LiteLLM、自托管模型等调用方式。
- 处理 streaming response。
- 统计 token。
- 估算成本。
- 处理 prompt cache。
- 管理 LiteLLM 初始化和 monkey patch。

重要目录/文件：

| 目录/文件 | 作用 |
|---|---|
| `factory.py` | 根据 persona/user/config 创建 LLM |
| `interfaces.py` | LLM 抽象接口 |
| `multi_llm.py` | 多模型并行调用 |
| `model_response.py` | 模型响应结构转换 |
| `litellm_singleton/` | LiteLLM 初始化和 patch |
| `prompt_cache/` | prompt cache provider 实现 |
| `well_known_providers/` | 常见 provider 元数据 |

项目要求所有 LLM、embedding、rerank、image、voice、intent-classification 调用都要使用 `LLMFlow` 做 tracing。新加 LLM 调用时要先检查 `backend/onyx/tracing/flows.py`。

### 5.9 `backend/onyx/tools`

`tools` 是 Agent 工具系统。

它负责把内部能力包装成 LLM 可调用的工具，例如：

- 搜索企业知识库。
- Web Search。
- 打开 URL。
- 读取文件。
- 代码执行。
- MCP 工具。
- 外部应用动作。

聊天时 Persona 会决定当前 Agent 可使用哪些工具。工具调用结果既要返回给 LLM，也要转换成前端能展示的 packet 和数据库可保存的结构。

### 5.10 `backend/onyx/auth` 与 `backend/onyx/access`

`auth` 处理身份认证，`access` 处理资源访问控制。

支持的认证能力包括：

- Basic auth
- Cloud auth
- OAuth
- OIDC
- SAML
- API Key
- Personal Access Token

权限检查通常通过 FastAPI dependency 完成，例如 `require_permission(...)`。文档、聊天文件、Persona、管理接口、连接器等资源也有各自访问判断。

### 5.11 `backend/onyx/file_processing` 与 `backend/onyx/file_store`

`file_processing` 负责文件解析、内容抽取、用户上传文件处理等。

`file_store` 是文件存储抽象，支持不同后端，例如对象存储、本地或 PostgreSQL large object。索引任务中的文档批次、用户上传文件、图片等都可能走这层。

### 5.12 `backend/onyx/redis`

`redis` 封装 Redis 连接、tenant client、docprocessing 状态、分布式锁、stop signal、队列协调等。

Redis 在 Onyx 中不只是缓存，也承担运行时协调：

- Celery broker。
- worker heartbeat。
- 索引任务锁。
- stop generation signal。
- tenant work gating。
- 临时状态存储。

### 5.13 `backend/onyx/kg`

`kg` 是知识图谱模块。

主要包括：

- 实体类型配置。
- 实体抽取。
- 聚类。
- KG reset/setup。
- Vespa KG 交互。

这部分用于在普通 RAG 检索之外增强实体、关系和结构化知识能力。

### 5.14 `backend/onyx/onyxbot`

`onyxbot` 是 Slack / Discord bot 集成层。

它把 Onyx 的搜索和聊天能力接入协作软件，使用户可以在 Slack 或 Discord 中直接提问、触发回答、管理 thread 上下文。

### 5.15 `backend/onyx/mcp_server`

`mcp_server` 提供 MCP server 能力，让外部 MCP client 或 Agent 通过 MCP 协议使用 Onyx 的搜索、Web Search、URL 打开等能力。

它本身有 FastAPI wrapper，但通常会把具体业务请求委托给 API server。

### 5.16 `backend/onyx/tracing`

`tracing` 负责 LLM flow tracing 和系统调用追踪。

重点是 `LLMFlow` 注册表。所有模型相关调用都应该标记所属业务流，避免 dashboard 中出现未标记的 `UNTAGGED_INVOKE` 或 `UNTAGGED_STREAM`。

### 5.17 `backend/ee`

`backend/ee` 是企业版扩展代码，与社区版 `backend/onyx` 并列。

常见企业版能力包括：

- 多租户。
- 企业认证。
- SCIM。
- 高级权限。
- 计费。
- license。
- feature flags。
- 企业搜索扩展。
- 企业级 telemetry。

社区版代码中常见 `fetch_ee_implementation_or_noop`、`fetch_versioned_implementation` 这类机制，用来按部署版本选择 CE 或 EE 实现。

### 5.18 `backend/alembic` 与 `backend/alembic_tenants`

`backend/alembic` 是主数据库迁移目录。

`backend/alembic_tenants` 是多租户相关迁移目录。

新增数据库结构时通常通过 Alembic 生成 migration 文件，然后手写 migration 内容。

## 6. 核心业务对象

理解以下对象有助于快速读懂业务代码。

| 对象 | 含义 |
|---|---|
| User | 用户 |
| Connector | 数据源配置，例如 Slack、Google Drive、Confluence |
| Credential | 访问外部系统的凭据 |
| ConnectorCredentialPair / CC Pair | connector 和 credential 的绑定，是实际索引任务的核心单位 |
| Document | 外部文档在 Onyx 中的统一表示 |
| Section | 文档内部片段，可为文本、图片、表格 |
| Chunk | 被检索系统索引的文本切片 |
| IndexAttempt | 一次索引尝试的状态记录 |
| SearchSettings | 当前搜索、embedding、index 配置 |
| Persona | Assistant/Agent 配置，包括 prompt、工具、模型、知识范围 |
| ChatSession | 一次聊天会话 |
| ChatMessage | 聊天消息 |
| Tool | LLM 可调用工具 |
| Skill | 可复用能力包 |
| DocumentSet | 文档集合，用于限定知识范围 |
| UserFile | 用户上传文件 |

其中 CC Pair 很关键。它代表“用某个凭据去同步某个连接器配置”，后台任务通常围绕 CC Pair 创建索引尝试。

## 7. 文档接入与索引链路

文档索引链路是后端最重要的异步流程之一。

### 7.1 管理员配置连接器

管理员在前端配置数据源，例如 Google Drive、Slack、Confluence。后端会创建：

- Connector
- Credential
- ConnectorCredentialPair

这些状态保存在 PostgreSQL。

### 7.2 Beat / Primary 扫描待处理任务

Celery Beat 定时触发检查任务。Primary worker 扫描需要索引的 CC Pair，并派发 docfetching task。

这一步的职责是“发现该做什么”，而不是直接拉文档。

### 7.3 Docfetching 抓取外部文档

Docfetching worker 根据 connector 类型调用对应 `backend/onyx/connectors/*` 代码。

它会：

1. 加载 connector 配置。
2. 加载 credential。
3. 调外部 API。
4. 处理分页和 checkpoint。
5. 把外部数据转成统一 `Document`。
6. 将文档批次暂存。
7. 派发 docprocessing task。

### 7.4 Docprocessing 处理文档

Docprocessing worker 调用 `indexing_pipeline`。

它会：

1. upsert 文档元数据到 PostgreSQL。
2. 记录索引 attempt 状态。
3. 处理文档权限和 metadata。
4. chunking。
5. 生成 embedding。
6. 写入 Vespa/OpenSearch。
7. 更新索引状态和 metrics。

### 7.5 搜索索引写入

`document_index` 层根据配置选择 Vespa 或 OpenSearch。写入的是 chunk 级别内容，同时保留文档 metadata、权限、source、boost、链接等信息。

后续搜索和聊天检索都依赖这些索引。

## 8. 聊天与 RAG 链路

聊天链路从 `backend/onyx/server/query_and_chat/chat_backend.py` 进入。

### 8.1 前端发起聊天请求

前端通常通过 `/api/chat/...` 请求后端。项目约定做后端调用时尽量通过前端地址 `http://localhost:3000/api/...`，不要直接打 `http://localhost:8080/...`，这样更接近真实部署路径。

### 8.2 API 层处理

API 层会：

1. 校验登录用户。
2. 检查权限。
3. 读取请求参数。
4. 加载会话或创建会话。
5. 调用聊天核心逻辑。
6. 以 StreamingResponse 返回 SSE/packet，或返回完整响应。

### 8.3 加载 Agent 配置

后端会加载 Persona，也就是当前 Assistant/Agent 的配置：

- 使用哪个模型。
- 系统 prompt。
- 是否替换默认系统 prompt。
- 可用工具。
- 可访问的 document set。
- 温度等模型参数。

### 8.4 检索上下文

如果当前 Agent 需要知识库搜索，系统会通过内部搜索工具从 Vespa/OpenSearch 召回相关 chunk。

检索会考虑：

- 用户问题。
- 聊天历史。
- 文档集过滤。
- source 过滤。
- metadata 过滤。
- 用户权限。
- embedding/关键词混合检索。
- rerank 或 LLM 文档选择。

### 8.5 组装 Prompt

Prompt 不只是用户输入，还包含：

- 默认 system prompt。
- Persona 自定义 prompt。
- 聊天历史。
- 项目上下文。
- 用户上传文件上下文。
- 搜索结果。
- 工具描述。
- 引用规则 reminder。

这些上下文会按 token 限制做裁剪或压缩。

### 8.6 LLM Loop 与工具调用

聊天核心进入 `llm_loop`：

```text
LLM 生成
  -> 如果需要工具，执行工具
  -> 把工具结果回填给 LLM
  -> 继续生成
  -> 直到得到最终回答
```

工具可能包括：

- 企业知识库搜索。
- Web Search。
- 文件读取。
- URL 打开。
- 代码执行。
- MCP 工具。
- 外部应用动作。

### 8.7 流式返回与保存

回答过程中，后端通过 StreamingResponse 持续返回 packet。生成结束后保存：

- 用户消息。
- Assistant 消息。
- 工具调用。
- 引用。
- token / usage。
- 反馈状态。

如果用户点击停止生成，后端通过 Redis stop signal 中断流式输出，并保存 partial state。

## 9. 搜索与权限过滤

Onyx 的搜索不是单纯语义搜索。

它通常会组合：

- 向量检索。
- 关键词检索。
- metadata 过滤。
- source 过滤。
- document set 过滤。
- 用户/用户组权限过滤。
- rerank。
- LLM 文档选择。

权限过滤非常关键。企业知识库不能让用户通过 AI 问答看到自己无权访问的文档。因此连接器同步时会尽量同步文档 ACL、外部用户、外部 group 等信息；检索时再根据当前用户身份过滤结果。

## 10. 错误处理规范

项目要求新代码使用统一错误处理：

```python
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError

raise OnyxError(OnyxErrorCode.NOT_FOUND, "Session not found")
```

不要在新代码中直接使用：

```python
from fastapi import HTTPException
raise HTTPException(status_code=404, detail="...")
```

如果转发上游服务的动态状态码，可以使用：

```python
raise OnyxError(
    OnyxErrorCode.BAD_GATEWAY,
    detail,
    status_code_override=upstream_status,
)
```

统一错误处理会把业务异常转换成标准 JSON：

```json
{
  "error_code": "...",
  "detail": "..."
}
```

## 11. 测试与开发注意事项

测试前需要先激活虚拟环境：

```bash
source .venv/bin/activate
```

常见测试类型：

| 类型 | 命令 | 说明 |
|---|---|---|
| Unit tests | `pytest -xv backend/tests/unit` | 不依赖外部服务，尽量 mock |
| External dependency unit tests | `python -m dotenv -f .vscode/.env run -- pytest backend/tests/external_dependency_unit` | 依赖 Postgres、Redis、Vespa、OpenAI 等外部服务，但不依赖 Onyx 容器 |
| Integration tests | `python -m dotenv -f .vscode/.env run -- pytest backend/tests/integration` | 跑在真实 Onyx 部署上 |
| Playwright E2E | `bunx playwright test <TEST_NAME>` | 前后端完整链路 |

调试运行中服务时，可以看：

```text
backend/log/<service_name>_debug.log
```

如果改了 Celery worker 代码，需要重启对应 worker。Celery worker 不会因为代码变化自动 reload。

## 12. 新人读代码建议

### 12.1 想看 API 怎么进来

从这里开始：

```text
backend/onyx/main.py
backend/onyx/server/query_and_chat/chat_backend.py
backend/onyx/server/documents/
backend/onyx/server/features/
backend/onyx/server/manage/
```

重点看 router、dependency、调用了哪些 `db` 函数和业务模块。

### 12.2 想看数据库模型

从这里开始：

```text
backend/onyx/db/models.py
backend/onyx/db/engine/
backend/onyx/db/chat.py
backend/onyx/db/document.py
backend/onyx/db/connector_credential_pair.py
backend/onyx/db/persona.py
```

先理解核心表：User、Connector、Credential、ConnectorCredentialPair、Document、IndexAttempt、Persona、ChatSession、ChatMessage。

### 12.3 想看文档怎么被索引

从这里开始：

```text
backend/onyx/connectors/models.py
backend/onyx/connectors/factory.py
backend/onyx/background/celery/tasks/docfetching/tasks.py
backend/onyx/background/celery/tasks/docprocessing/tasks.py
backend/onyx/indexing/indexing_pipeline.py
backend/onyx/document_index/factory.py
```

建议按“connector -> docfetching -> docprocessing -> indexing_pipeline -> document_index”顺序读。

### 12.4 想看聊天怎么回答

从这里开始：

```text
backend/onyx/server/query_and_chat/chat_backend.py
backend/onyx/chat/process_message.py
backend/onyx/chat/llm_loop.py
backend/onyx/chat/llm_step.py
backend/onyx/chat/prompt_utils.py
backend/onyx/tools/
backend/onyx/llm/factory.py
```

建议按“API -> process_message -> llm_loop -> tools/search -> llm”顺序读。

### 12.5 想看模型配置

从这里开始：

```text
backend/onyx/server/manage/llm/
backend/onyx/db/llm.py
backend/onyx/llm/factory.py
backend/onyx/llm/litellm_singleton/
```

### 12.6 想看权限

从这里开始：

```text
backend/onyx/auth/
backend/onyx/access/
backend/onyx/db/permissions.py
backend/onyx/db/document_access.py
backend/onyx/server/auth_check.py
```

权限逻辑贯穿 API、搜索和文档访问，不能只看一个文件。

## 13. 后端目录速查表

| 目录 | 简要说明 |
|---|---|
| `backend/onyx/main.py` | FastAPI 应用入口 |
| `backend/onyx/server` | API 路由层 |
| `backend/onyx/db` | ORM 模型和数据库访问 |
| `backend/onyx/connectors` | 外部数据源连接器 |
| `backend/onyx/background` | Celery 后台任务 |
| `backend/onyx/indexing` | 文档处理与索引流水线 |
| `backend/onyx/document_index` | Vespa/OpenSearch 抽象与实现 |
| `backend/onyx/chat` | 聊天和 RAG 编排 |
| `backend/onyx/llm` | LLM provider 抽象 |
| `backend/onyx/tools` | Agent 工具 |
| `backend/onyx/auth` | 认证 |
| `backend/onyx/access` | 访问控制 |
| `backend/onyx/cache` | 缓存抽象 |
| `backend/onyx/redis` | Redis 连接、锁、运行时协调 |
| `backend/onyx/file_processing` | 文件解析处理 |
| `backend/onyx/file_store` | 文件存储抽象 |
| `backend/onyx/federated_connectors` | 联邦搜索连接器 |
| `backend/onyx/kg` | 知识图谱 |
| `backend/onyx/mcp_server` | MCP server |
| `backend/onyx/onyxbot` | Slack/Discord bot |
| `backend/onyx/prompts` | prompt 模板 |
| `backend/onyx/tracing` | tracing 和 LLMFlow |
| `backend/onyx/utils` | 通用工具 |
| `backend/ee` | 企业版后端扩展 |
| `backend/model_server` | 本地模型服务 |
| `backend/alembic` | 数据库迁移 |
| `backend/alembic_tenants` | 多租户迁移 |
| `backend/tests` | 后端测试 |
| `backend/scripts` | 运维、调试、迁移辅助脚本 |
| `backend/requirements` | Python 依赖清单 |

## 14. 总结

Onyx 后端的核心不是某一个单独模块，而是多个模块协作形成的企业 RAG 平台。

最重要的理解路径有两条：

```text
知识进入系统：
connectors -> Celery -> indexing -> document_index -> searchable chunks
```

```text
用户获得答案：
server/chat API -> chat orchestration -> search/tools -> llm -> streaming response
```

如果要做二次开发，建议先明确改动落在哪一层：

- 改 API：看 `server`。
- 改数据表：看 `db` 和 `alembic`。
- 加数据源：看 `connectors`、`background`、`indexing`。
- 改检索：看 `document_index`、`indexing`、`server/query_and_chat`。
- 改聊天行为：看 `chat`、`tools`、`llm`。
- 改 Agent 能力：看 `persona`、`tools`、`skills`、`mcp`。
- 改企业权限/租户：看 `auth`、`access`、`db`、`ee`。

掌握这几层之后，再看具体文件会容易很多。
