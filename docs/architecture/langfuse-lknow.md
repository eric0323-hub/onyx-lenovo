**Onyx + Langfuse 集成实施方案**

**版本**：v2.0
**日期**：2026-06-02
**目标**：将 Langfuse 作为 Onyx 的可观测性控制台接入，实现同一域名子路径访问、统一 OIDC/SSO、Onyx 后端自动上报 LLM tracing，并保留 Onyx 现有 `LLMFlow` 语义和 tracing 抽象。

---

## 1. 结论

本方案可行，但旧方案中有几处技术点必须修正：

1. Langfuse 部署在 `/observability` 子路径时，`langfuse-web` 不能直接使用预构建镜像。Langfuse v3 官方要求用 `NEXT_PUBLIC_BASE_PATH=/observability` 从源码构建 web 镜像，因为 base path 会内联进静态资源。`langfuse-worker` 可以继续使用预构建镜像。
2. `NEXTAUTH_URL` 必须包含 base path 和 `/api/auth`，例如 `https://onyx.yourcompany.com/observability/api/auth`，不是只写到 `/observability`。
3. Onyx 的 OIDC 配置变量是 `AUTH_TYPE=oidc`、`OPENID_CONFIG_URL`、`OAUTH_CLIENT_ID`、`OAUTH_CLIENT_SECRET`，不是 `OIDC_DISCOVERY_URL` / `OIDC_CLIENT_ID`。
4. Langfuse 对 Keycloak 的 SSO 变量是 `AUTH_KEYCLOAK_CLIENT_ID`、`AUTH_KEYCLOAK_CLIENT_SECRET`、`AUTH_KEYCLOAK_ISSUER`。如果不用内置 Keycloak provider，才使用 `AUTH_CUSTOM_*`。
5. Onyx 已经有 Langfuse tracing processor，不应在业务代码里直接散落 `langfuse.decorators.observe` 或 `langfuse.trace(...)`。正确方式是启用现有 processor，并在缺失业务流的调用点补 Onyx 自有 `trace` / `ensure_trace` / `llm_generation_span` / `traced_llm_call`。
6. “同一登录态”应理解为同一个 OIDC Provider 的 SSO 登录态。Onyx 和 Langfuse 的应用 session cookie 不共享，只是用户在同一 IdP 下可以无感或少交互登录两边。

### 1.1 推荐决策

如果必须做到“同一域名 + 子路径”，采用本文主方案：`https://onyx.yourcompany.com/observability`。代价是需要维护自定义构建的 `langfuse-web` 镜像，并严格控制反向代理 rewrite。

如果团队更看重运维稳定性，优先使用独立子域名：`https://langfuse.yourcompany.com`。该方案可以直接使用 Langfuse 官方预构建 web 镜像，OIDC 和 Onyx tracing 配置不变，只是 Onyx 菜单入口和 `LANGFUSE_HOST` 改成独立域名。

### 1.2 非目标

本方案不把 Langfuse 嵌入为 iframe，不改造 Langfuse UI，不让 Onyx 接管 Langfuse 的授权逻辑，也不把 Langfuse API key 暴露给 Onyx 前端。Langfuse 仍作为独立应用运行，只是在访问路径、SSO 和 tracing 数据上与 Onyx 打通。

---

## 2. 目标架构

```text
Browser
  |
  | https://onyx.yourcompany.com/
  v
Reverse Proxy
  |-- /                         -> Onyx web/API
  |-- /observability/            -> Langfuse web, built with NEXT_PUBLIC_BASE_PATH=/observability
  |
  | OIDC redirects
  v
Keycloak / Authentik / other IdP

Onyx API server / Celery workers
  |
  | Langfuse SDK, LANGFUSE_HOST=https://onyx.yourcompany.com/observability
  v
Langfuse ingestion API
  |
  |-- Postgres       application metadata
  |-- ClickHouse     traces/events/observations
  |-- Redis          queues/cache
  |-- S3/MinIO       blob/event/media storage
```

推荐把 Langfuse 看成独立产品部署在 Onyx 域名下，而不是 Onyx 内部页面。Onyx 只负责：

- 提供入口菜单。
- 通过统一 IdP 做登录。
- 通过 `backend/onyx/tracing` 自动上报 trace。
- 可选地通过后端代理读取 Langfuse 汇总数据展示在 Onyx dashboard。

---

## 3. 现有 Onyx tracing 状态

当前仓库已经具备 Langfuse 接入基础：

- `pyproject.toml` 已包含 `langfuse==3.10.0`，不需要再手动 `pip install langfuse`。
- `backend/onyx/tracing/setup.py` 会在配置 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY` 后注册 `LangfuseTracingProcessor`。
- `backend/onyx/main.py` 在 API server 启动时调用 `setup_tracing()`。
- `backend/onyx/background/celery/apps/app_base.py` 在 Celery worker 启动时调用 `setup_tracing()`。
- `backend/onyx/tracing/langfuse_tracing_processor.py` 负责把 Onyx trace framework 转成 Langfuse observations。
- `backend/onyx/tracing/llm_utils.py` 提供 `llm_generation_span`、`traced_llm_call`、`record_llm_response`、`record_llm_span_output`。
- `backend/onyx/tracing/flows.py` 是 `LLMFlow` 注册表。
- `backend/onyx/llm/tracing_wrap.py` 提供 fallback tracing，出现 `UNTAGGED_INVOKE` / `UNTAGGED_STREAM` 代表调用点缺少明确业务 flow。

Langfuse processor 当前映射规则：

- trace metadata 中的 `chat_session_id` 会提升为 Langfuse `session_id`。
- trace metadata 中的 `user_id` 会提升为 Langfuse `user_id`。
- generation span 会写入 `model`、`model_parameters`、`usage_details`、`cost_details`、input/output。
- input/output 默认经过 `onyx.tracing.masking.mask_sensitive_data` 脱敏。
- span error 会映射为 Langfuse observation 的 error level/status message。

因此，后端集成的主要工作是配置和补齐缺失 span，不是重新设计 Langfuse SDK 埋点。

### 3.1 Langfuse 字段映射

当前 `LangfuseTracingProcessor` 的行为如下：

| Onyx trace/span 数据 | Langfuse 字段 | 说明 |
| --- | --- | --- |
| `trace.name` | trace name / root observation name | processor 会创建一个 root observation，并用 trace name 更新 Langfuse trace。 |
| `trace.metadata["chat_session_id"]` | `session_id` | 只有 key 名为 `chat_session_id` 时会自动提升；其他 session 字段只留在 metadata 中。 |
| `trace.metadata["user_id"]` | `user_id` | 会转成 string。没有该字段时 Langfuse user facet 为空。 |
| `trace.metadata` | trace metadata、child observation metadata | 会传给 Langfuse，用于筛选和排查。 |
| first span input | root observation input | trace 结束时，processor 用第一个非空 span input 更新 root observation。 |
| last span output | root observation output | trace 结束时，processor 用最后一个非空 span output 更新 root observation。 |
| `GenerationSpanData` | `generation` observation | 包含 model、model parameters、input/output、usage/cost。 |
| `FunctionSpanData` | `tool` observation | input/output 会经过 masking 后写入。 |
| `AgentSpanData` | `agent` observation | tools、handoffs、output_type 会写入 metadata。 |
| `span.error` | observation `level=ERROR` + status message | 用于在 Langfuse UI 中标出错误 observation。 |

当前 processor 的几个重要限制：

- `trace.group_id` 没有直接映射成 Langfuse `session_id`；要显示在 Langfuse session 维度，需要在 metadata 中显式放 `chat_session_id`。
- generation observation 名称当前是 `Generation with {model}`，业务 flow 存在 `model_config["flow"]` 中，不是 observation name。
- `model_parameters` 只提取 `temperature`、`max_tokens`、`top_p`、`frequency_penalty`、`presence_penalty`。provider、base URL、flow 等会留在 model config，不一定出现在 Langfuse 的 model parameter facet 中。
- `reasoning` 会作为 observation metadata 写入。若 reasoning 内容被视为敏感数据，应在调用点避免记录或扩展 masking。
- 没有 active trace 时，Onyx trace provider 会返回 `NoOpSpan`，因此不会上报到 Langfuse。排查“没有 trace”时先确认外层是否有 `trace(...)` 或 `ensure_trace(...)`。

### 3.2 Masking 和数据治理

当前 masking 主要做三件事：

- 递归处理 dict/list。
- 对 key 包含 `private_key` 或 `authorization` 的字段做 `***REDACTED***`。
- 对字符串中的 `Authorization: Bearer ...` 和包含 `private_key` 的内容做脱敏，并按 `TRACING_MASKING_LENGTH` 截断超长内容。

这不是完整的 DLP。它不会默认识别所有邮箱、手机号、SSN、身份证号、API key、OAuth refresh token、数据库连接串或业务私密字段。生产启用前必须确认：

- 哪些 prompt、retrieved context、tool output 可以进入 Langfuse。
- 哪些 metadata 字段允许外部可观测性系统保存。
- 是否需要扩展 `backend/onyx/tracing/masking.py` 的规则。
- `TRACING_MASKING_LENGTH` 是否过大。默认 `500000` 适合调试，但对生产成本和敏感内容暴露都偏宽。
- 是否需要按环境禁用 input/output 上报，或只上报 usage/cost/latency。

如果公司对数据出境或供应商隔离有要求，应把自托管 Langfuse 的部署区域、ClickHouse/Postgres/S3 保留周期、备份加密和访问审计纳入同一评审。

---

## 4. 部署前提

### 4.1 必需组件

- Onyx 已可通过 `https://onyx.yourcompany.com` 访问。
- 一个 OIDC Provider，例如 Keycloak、Authentik、Okta、Azure AD/Entra ID。
- Langfuse v3 平台。
- Langfuse 所需基础设施：Postgres、ClickHouse、Redis、对象存储。
- 反向代理，例如 Nginx、Traefik、Ingress NGINX。

### 4.2 生产建议

- Langfuse 的 Postgres、ClickHouse、Redis、对象存储建议和 Onyx 分开管理。开发环境可以共用底层集群，但必须使用独立 database、credential、bucket、Redis namespace 或独立 Redis 实例。
- ClickHouse 是 Langfuse v3 的核心存储，不应省略。
- Onyx `LANGFUSE_SECRET_KEY` 只放在后端和 worker 环境变量里，不进入浏览器。
- Langfuse UI 里会出现 prompt、响应、metadata、token usage 等敏感数据，必须对访问权限、保留周期、脱敏策略做生产级配置。

### 4.3 版本兼容

| 组件 | 本仓库当前状态 | 要求 / 建议 |
| --- | --- | --- |
| Onyx Python SDK 依赖 | `langfuse==3.10.0` | 不需要新增依赖；升级到 Langfuse Python SDK v4 前，必须先验证 `LangfuseTracingProcessor` 的 API 兼容性。 |
| Onyx tracing processor | 使用 `client.start_observation(...)`、`update_trace(...)`、`usage_details`、`cost_details` | 这是当前代码的集成边界。不要在业务代码直接调用 Langfuse SDK 绕过 processor。 |
| Langfuse platform | v3 | 自托管平台版本应与当前 SDK 能力兼容。按官方最新说明，Python SDK v3 的完整功能需要较新的 Langfuse v3 平台；生产不要用过旧平台镜像。 |
| Langfuse web 子路径 | 需要 build-time `NEXT_PUBLIC_BASE_PATH` | 只有 web 镜像需要自构建；worker 可用 `langfuse/langfuse-worker:3`。 |
| Onyx OIDC | `AUTH_TYPE=oidc` + `OPENID_CONFIG_URL` | 不使用旧式 `OIDC_DISCOVERY_URL` / `OIDC_CLIENT_ID` 变量。 |

版本升级原则：

- 先升级 Langfuse platform，再升级 Python SDK。
- 升级 SDK 后必须跑一次真实 trace 验证，确认 `generation` observation 的 model、usage、cost、input/output、trace user/session 都还存在。
- 如果 Langfuse SDK 构造参数从 `host` 切换到 `base_url` 或其他命名，优先改 `backend/onyx/tracing/setup.py`，不要在调用点分散兼容逻辑。

### 4.4 子路径与子域名对比

| 方案 | 优点 | 风险 / 成本 | 适用场景 |
| --- | --- | --- | --- |
| `/observability` 子路径 | 用户感知统一；Onyx 菜单跳转自然；同域证书和 cookie policy 简单 | 需要自构建 Langfuse web；代理不能 rewrite；升级时要重新构建 web 镜像 | 明确要求同一域名的一体化体验 |
| `langfuse.yourcompany.com` 子域名 | 可直接用官方镜像；反向代理最简单；升级成本低 | URL 不是 Onyx 子路径；用户能感知是独立控制台 | 生产稳定性优先，或不想维护自定义 web 镜像 |

### 4.5 多租户策略

Onyx 多租户环境下有两种 Langfuse 项目策略：

| 策略 | 做法 | 优点 | 风险 |
| --- | --- | --- | --- |
| 单 Langfuse project | 所有 tenant 共用一组 `LANGFUSE_*` key，metadata 写入 `tenant_id` | 运维简单，跨租户全局统计方便 | Langfuse project 内能看到所有 tenant 数据，必须严格控制 Langfuse 访问者 |
| 每 tenant 独立 project | 每个 tenant 使用独立 Langfuse project key | 数据隔离清晰，权限更容易按 tenant 管 | Onyx 启动配置和 worker 调度更复杂；当前 `setup_tracing()` 是进程级初始化，不支持在同一进程内按 tenant 动态切换 project |

基于当前 Onyx 代码，推荐先采用单 Langfuse project + `tenant_id` metadata 的方式；如果需要硬隔离，应先设计进程级/部署级 tenant 分片，而不是在调用点动态创建 Langfuse client。

---

## 5. OIDC Provider 配置

以下以 Keycloak 为例，其他 IdP 按同样思路配置。

### 5.1 Realm

- Realm: `onyx-realm`
- Issuer: `https://keycloak.yourcompany.com/realms/onyx-realm`
- Discovery URL: `https://keycloak.yourcompany.com/realms/onyx-realm/.well-known/openid-configuration`

### 5.2 Onyx client

- Client ID: `onyx-app`
- Client type: confidential client
- Standard flow: enabled
- Valid redirect URIs:
  - `https://onyx.yourcompany.com/auth/oidc/callback`
  - 开发环境按需增加 `http://localhost:3000/auth/oidc/callback`
- Web origins:
  - `https://onyx.yourcompany.com`

Onyx 前端的 `/auth/oidc/callback` 会代理到后端 `/auth/oidc/callback`，所以不要使用 `https://onyx.yourcompany.com/api/auth/callback/oidc`。

### 5.3 Langfuse client

如果使用 Langfuse 内置 Keycloak provider：

- Client ID: `langfuse-app`
- Client type: confidential client
- Standard flow: enabled
- Valid redirect URIs:
  - `https://onyx.yourcompany.com/observability/api/auth/callback/keycloak`
- Web origins:
  - `https://onyx.yourcompany.com`

如果改用 Langfuse custom OAuth provider，则 callback 是：

- `https://onyx.yourcompany.com/observability/api/auth/callback/custom`

### 5.4 Claims 和权限

最低 scopes：

- `openid`
- `email`
- `profile`

可选 scopes：

- `groups`，用于后续按 IdP group 控制访问。
- `offline_access`，Onyx 会在 OIDC auth flow 中自动补上，但 IdP 侧仍需允许。

注意：Onyx 侧边栏隐藏入口不等于安全控制。Langfuse 本身是独立应用，必须在 Langfuse/IdP 侧限制可登录用户，例如只允许 `observability-admins` group 访问 `langfuse-app`。

---

## 6. 配置 Onyx OIDC

在 Onyx API server、web server 相关环境中配置：

```env
AUTH_TYPE=oidc
WEB_DOMAIN=https://onyx.yourcompany.com

OPENID_CONFIG_URL=https://keycloak.yourcompany.com/realms/onyx-realm/.well-known/openid-configuration
OAUTH_CLIENT_ID=onyx-app
OAUTH_CLIENT_SECRET=<keycloak onyx-app secret>

# 可选。Onyx 代码按逗号拆分，不要写成空格分隔。
# 如果不配置，默认会请求 openid/email/profile，并在 OIDC flow 中追加 offline_access。
OIDC_SCOPE_OVERRIDE=openid,email,profile,groups

# 如果 IdP client 支持 PKCE，可开启。
OIDC_PKCE_ENABLED=true
```

旧方案中的这些变量不适用于当前 Onyx 代码：

```env
OIDC_DISCOVERY_URL=...
OIDC_CLIENT_ID=...
OIDC_CLIENT_SECRET=...
OIDC_ISSUER=...
OIDC_ALLOW_ACCOUNT_LINKING=...
SCIM_ENABLED=...
```

其中 SCIM 是单独的企业用户同步能力，不是启用 OIDC 登录或 Langfuse 集成的前提。

---

## 7. 部署 Langfuse 到 `/observability`

### 7.1 构建 Langfuse web 镜像

Langfuse v3 官方说明：自定义 base path 会进入静态资源，因此 `langfuse-web` 必须从源码构建。生产环境建议固定到明确 release/tag，不要长期跟随移动分支。

```bash
git clone https://github.com/langfuse/langfuse.git
cd langfuse

# 示例：使用 production 分支。生产推荐替换为明确 tag。
git checkout production

docker build \
  -t langfuse-web-observability:3 \
  --build-arg NEXT_PUBLIC_BASE_PATH=/observability \
  -f ./web/Dockerfile \
  .
```

`langfuse-worker` 不服务静态 web 资源，可以使用官方预构建镜像：

```text
docker.io/langfuse/langfuse-worker:3
```

### 7.2 Langfuse 环境变量

以下只列关键变量。完整基础设施变量以 Langfuse 官方 docker-compose 或 Helm values 为准。

```env
# URL / auth
NEXT_PUBLIC_BASE_PATH=/observability
NEXTAUTH_URL=https://onyx.yourcompany.com/observability/api/auth
NEXTAUTH_SECRET=<openssl rand -base64 32>

# Langfuse application secrets
SALT=<long random string>
ENCRYPTION_KEY=<openssl rand -hex 32>

# Database / infra
DATABASE_URL=postgresql://langfuse:<password>@langfuse-postgres:5432/langfuse
CLICKHOUSE_URL=http://clickhouse:8123
CLICKHOUSE_MIGRATION_URL=clickhouse://clickhouse:9000
CLICKHOUSE_USER=clickhouse
CLICKHOUSE_PASSWORD=<password>
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_AUTH=<password>

# Object storage, example only
LANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse
LANGFUSE_S3_EVENT_UPLOAD_REGION=auto
LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=<access key>
LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=<secret key>
LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=http://minio:9000
LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=true

LANGFUSE_S3_MEDIA_UPLOAD_BUCKET=langfuse
LANGFUSE_S3_MEDIA_UPLOAD_REGION=auto
LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID=<access key>
LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY=<secret key>
LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT=https://onyx.yourcompany.com/minio-or-s3
LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE=true

# SSO, Keycloak provider
AUTH_DISABLE_USERNAME_PASSWORD=true
AUTH_KEYCLOAK_CLIENT_ID=langfuse-app
AUTH_KEYCLOAK_CLIENT_SECRET=<keycloak langfuse-app secret>
AUTH_KEYCLOAK_ISSUER=https://keycloak.yourcompany.com/realms/onyx-realm
AUTH_KEYCLOAK_SCOPE=openid email profile groups
AUTH_KEYCLOAK_ALLOW_ACCOUNT_LINKING=true
```

如果使用 custom OAuth provider，替换为：

```env
AUTH_CUSTOM_CLIENT_ID=langfuse-app
AUTH_CUSTOM_CLIENT_SECRET=<secret>
AUTH_CUSTOM_ISSUER=https://keycloak.yourcompany.com/realms/onyx-realm
AUTH_CUSTOM_NAME=Company SSO
AUTH_CUSTOM_SCOPE=openid email profile groups
AUTH_CUSTOM_ALLOW_ACCOUNT_LINKING=true
```

账号合并风险：`AUTH_<PROVIDER>_ALLOW_ACCOUNT_LINKING=true` 只应在 IdP 邮箱已验证且可信时开启，否则可能出现同邮箱账号接管风险。

### 7.3 Compose 服务形态

不要只启动 `langfuse-web`。v3 至少需要：

- `langfuse-web`
- `langfuse-worker`
- Postgres
- ClickHouse
- Redis
- S3/MinIO 或等价对象存储

示意：

```yaml
services:
  langfuse-web:
    image: langfuse-web-observability:3
    restart: always
    environment:
      NEXT_PUBLIC_BASE_PATH: /observability
      NEXTAUTH_URL: https://onyx.yourcompany.com/observability/api/auth
      NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET}
      DATABASE_URL: ${LANGFUSE_DATABASE_URL}
      SALT: ${LANGFUSE_SALT}
      ENCRYPTION_KEY: ${LANGFUSE_ENCRYPTION_KEY}
      CLICKHOUSE_URL: http://clickhouse:8123
      CLICKHOUSE_MIGRATION_URL: clickhouse://clickhouse:9000
      CLICKHOUSE_USER: ${CLICKHOUSE_USER}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD}
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_AUTH: ${LANGFUSE_REDIS_AUTH}
      AUTH_DISABLE_USERNAME_PASSWORD: "true"
      AUTH_KEYCLOAK_CLIENT_ID: langfuse-app
      AUTH_KEYCLOAK_CLIENT_SECRET: ${LANGFUSE_KEYCLOAK_CLIENT_SECRET}
      AUTH_KEYCLOAK_ISSUER: https://keycloak.yourcompany.com/realms/onyx-realm
      AUTH_KEYCLOAK_SCOPE: openid email profile groups
      AUTH_KEYCLOAK_ALLOW_ACCOUNT_LINKING: "true"
    ports:
      - "3001:3000"

  langfuse-worker:
    image: docker.io/langfuse/langfuse-worker:3
    restart: always
    environment:
      NEXTAUTH_URL: https://onyx.yourcompany.com/observability/api/auth
      DATABASE_URL: ${LANGFUSE_DATABASE_URL}
      SALT: ${LANGFUSE_SALT}
      ENCRYPTION_KEY: ${LANGFUSE_ENCRYPTION_KEY}
      CLICKHOUSE_URL: http://clickhouse:8123
      CLICKHOUSE_MIGRATION_URL: clickhouse://clickhouse:9000
      CLICKHOUSE_USER: ${CLICKHOUSE_USER}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD}
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_AUTH: ${LANGFUSE_REDIS_AUTH}
```

以上不是可直接复制的完整 compose，只是 Onyx 集成相关关键项。完整文件应从 Langfuse 官方 `docker-compose.yml` 或 Helm chart 派生。

---

## 8. 反向代理配置

关键点：因为 `langfuse-web` 已用 `/observability` 构建，代理到 upstream 时不要剥离 `/observability` 前缀。

Nginx 示例：

```nginx
location = /observability {
    return 308 /observability/;
}

location /observability/ {
    proxy_pass http://langfuse-web:3000;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Prefix /observability;

    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
}

location / {
    proxy_pass http://onyx-web:3000;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

旧方案中的写法有风险：

```nginx
location /observability/ {
    proxy_pass http://langfuse-web:3000/;
}
```

这个 trailing slash 通常会让 Nginx 把 `/observability/` 前缀剥掉，导致使用 base path 构建的 Next.js 应用路由和静态资源路径不匹配。

Kubernetes/Helm 注意事项：

- Ingress path 也不要 rewrite 掉 `/observability`。
- Langfuse web liveness/readiness probe path 要包含 `/observability`。
- 如果使用 Ingress NGINX 的 rewrite annotation，需要专门为 Langfuse location 关闭或拆成独立 Ingress。

---

## 9. 启用 Onyx 到 Langfuse 的 tracing

### 9.1 创建 Langfuse project 和 API keys

登录 Langfuse 后创建一个 project，例如：

- Organization: `Onyx`
- Project: `onyx-prod`

复制该 project 的：

- Public key
- Secret key

### 9.2 配置 Onyx 环境变量

这些变量必须配置到所有会产生 trace 的 Onyx 进程：

- API server
- Celery primary worker
- Celery docprocessing worker
- Celery docfetching worker
- Celery light/heavy/user_file_processing/monitoring worker
- Slack/Discord bot 或其他会调用 LLM 的独立进程

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://onyx.yourcompany.com/observability
```

注意：Langfuse 较新的官方 SDK 文档可能使用 `LANGFUSE_BASE_URL`。当前 Onyx 代码读取的是 `LANGFUSE_HOST`，并在 `backend/onyx/tracing/setup.py` 中传给 `Langfuse(..., host=...)`。除非同步改 Onyx tracing setup，否则不要只配置 `LANGFUSE_BASE_URL`。

如果只配置 API server，不配置 Celery worker，则聊天接口可能有 trace，但文档处理、图片总结、contextual RAG、权限同步中的模型调用不会完整进入 Langfuse。

### 9.2.1 Onyx 服务配置落点

当前仓库的 Docker Compose 主文件是 `deployment/docker_compose/docker-compose.yml`：

- `api_server`
- `background`，该服务通过 supervisord 启动多个后台 worker
- `web_server`，不需要 Langfuse secret，除非只放公开入口路径配置

拆分式部署或 Helm 部署中，需要覆盖所有会调用模型或产生 trace 的进程：

- API server
- Celery primary / docfetching / docprocessing / light / heavy / monitoring / user_file_processing
- 如果启用 Craft 或定时任务中的 LLM 能力，也包括 scheduled tasks worker
- Slack / Discord / MCP 等独立进程如果会调用 LLM，也要配置

Onyx web 前端只需要可选公开变量：

```env
NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH=/observability
```

不要把 `LANGFUSE_SECRET_KEY`、Langfuse Basic Auth token、Langfuse project secret 放到 `web` 的 `NEXT_PUBLIC_*` 中。

如果使用 multi-tenant，各 tenant 共享同一个 Langfuse project 时，必须确保 trace metadata 写入 `tenant_id`；如果需要租户隔离，则每个 tenant 使用不同 Langfuse project key，并在启动配置层面区分。

### 9.2.2 环境变量总表

| 配置对象 | 变量 | 必需 | 放置位置 | 说明 |
| --- | --- | --- | --- | --- |
| Onyx API / worker | `LANGFUSE_PUBLIC_KEY` | 是 | Secret / `.env` | Langfuse project public key。 |
| Onyx API / worker | `LANGFUSE_SECRET_KEY` | 是 | Secret / `.env` | 只进入后端和 worker，不进入浏览器公开配置。 |
| Onyx API / worker | `LANGFUSE_HOST` | 是 | ConfigMap / `.env` | 子路径方案写 `https://onyx.yourcompany.com/observability`；子域名方案写 `https://langfuse.yourcompany.com`。当前 Onyx 代码读取这个变量，不读取 `LANGFUSE_BASE_URL`。 |
| Onyx API / worker | `TRACING_MASKING_LENGTH` | 否 | ConfigMap / `.env` | 控制 trace input/output 最大保留长度；生产建议按数据策略调小。 |
| Onyx web | `NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH` | 否 | 前端 build arg / runtime public config | 仅用于显示前端入口，例如 `/observability`。不能承载 secret；当前 `web/Dockerfile` 需要同步新增 `ARG` / `ENV` 后才会进入构建。 |
| Onyx OIDC | `AUTH_TYPE` | 是 | ConfigMap / `.env` | OIDC 登录时为 `oidc`。 |
| Onyx OIDC | `WEB_DOMAIN` | 是 | ConfigMap / `.env` | 例如 `https://onyx.yourcompany.com`。 |
| Onyx OIDC | `OPENID_CONFIG_URL` | 是 | ConfigMap / `.env` | IdP discovery URL。 |
| Onyx OIDC | `OAUTH_CLIENT_ID` | 是 | ConfigMap / `.env` | Onyx IdP client id，例如 `onyx-app`。 |
| Onyx OIDC | `OAUTH_CLIENT_SECRET` | 是 | Secret / `.env` | Onyx IdP client secret。 |
| Onyx OIDC | `OIDC_SCOPE_OVERRIDE` | 否 | ConfigMap / `.env` | 逗号分隔，例如 `openid,email,profile,groups`。 |
| Onyx OIDC | `OIDC_PKCE_ENABLED` | 否 | ConfigMap / `.env` | IdP 支持 PKCE 时可设为 `true`。 |
| Langfuse web | `NEXT_PUBLIC_BASE_PATH` | 子路径方案必需 | build arg + runtime env | `/observability`，必须用于构建 `langfuse-web` 镜像。 |
| Langfuse web / worker | `NEXTAUTH_URL` | 是 | Secret 或 ConfigMap | 子路径方案必须是 `https://onyx.yourcompany.com/observability/api/auth`。 |
| Langfuse web / worker | `NEXTAUTH_SECRET` | 是 | Secret | NextAuth 加密 secret。 |
| Langfuse web / worker | `SALT`、`ENCRYPTION_KEY` | 是 | Secret | Langfuse 应用级密钥。 |
| Langfuse web / worker | `DATABASE_URL` | 是 | Secret | Langfuse 自己的 Postgres，不要复用 Onyx database/schema。 |
| Langfuse web / worker | `CLICKHOUSE_URL`、`CLICKHOUSE_MIGRATION_URL`、`CLICKHOUSE_USER`、`CLICKHOUSE_PASSWORD` | 是 | Secret / ConfigMap | ClickHouse 是 Langfuse v3 trace/event 核心存储。 |
| Langfuse web / worker | `REDIS_HOST`、`REDIS_PORT`、`REDIS_AUTH` | 是 | Secret / ConfigMap | 建议与 Onyx Redis 隔离；如共用实例，至少隔离 DB/namespace。 |
| Langfuse web / worker | `LANGFUSE_S3_*` | 是 | Secret / ConfigMap | 对象存储配置；生产配置 lifecycle 和备份策略。 |
| Langfuse auth | `AUTH_DISABLE_USERNAME_PASSWORD` | 建议 | ConfigMap | 生产 SSO 场景建议设为 `true`。 |
| Langfuse auth | `AUTH_KEYCLOAK_CLIENT_ID`、`AUTH_KEYCLOAK_CLIENT_SECRET`、`AUTH_KEYCLOAK_ISSUER` | Keycloak 方案必需 | Secret / ConfigMap | callback 为 `/observability/api/auth/callback/keycloak`。 |
| Langfuse auth | `AUTH_CUSTOM_CLIENT_ID`、`AUTH_CUSTOM_CLIENT_SECRET`、`AUTH_CUSTOM_ISSUER` | custom OAuth 方案必需 | Secret / ConfigMap | callback 为 `/observability/api/auth/callback/custom`。 |

### 9.2.3 Docker Compose 配置模板

当前 compose 文件的 `api_server` 和 `background` 都读取 `deployment/docker_compose/.env`，理论上把 `LANGFUSE_*` 写入 `.env` 即可被容器继承。为了降低排查成本，生产建议同时在服务的 `environment` 中显式列出：

```yaml
services:
  api_server:
    env_file:
      - path: .env
        required: false
    environment:
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY:-}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY:-}
      - LANGFUSE_HOST=${LANGFUSE_HOST:-https://onyx.yourcompany.com/observability}
      - TRACING_MASKING_LENGTH=${TRACING_MASKING_LENGTH:-500000}

  background:
    env_file:
      - path: .env
        required: false
    environment:
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY:-}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY:-}
      - LANGFUSE_HOST=${LANGFUSE_HOST:-https://onyx.yourcompany.com/observability}
      - TRACING_MASKING_LENGTH=${TRACING_MASKING_LENGTH:-500000}
```

如果实现前端入口，`web_server` 只需要公开路径。因为 `NEXT_PUBLIC_*` 通常会进入前端构建产物，必须保证它在 web 镜像构建阶段可用。当前 `web/Dockerfile` 只声明了已有 public variables，新增 `NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH` 时需要在 builder 和 runner 两个阶段都加上：

```dockerfile
ARG NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH
ENV NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH=${NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH}
```

然后在 compose build args 中传入：

```yaml
services:
  web_server:
    build:
      args:
        - NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH=${NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH:-/observability}
    environment:
      - INTERNAL_URL=${INTERNAL_URL:-http://api_server:8080}
      - NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH=${NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH:-/observability}
```

对应 `.env` 示例：

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://onyx.yourcompany.com/observability
TRACING_MASKING_LENGTH=100000
NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH=/observability
```

修改后需要重启 `api_server` 和 `background`。只改 `.env` 不重启，不会重新执行 `setup_tracing()`。如果新增或修改 `NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH`，需要重新构建 `web_server` 镜像；单纯重启 web 容器通常不会更新已编译进 bundle 的 client-side public env。

### 9.2.4 Helm / Kubernetes 配置模板

当前 Helm chart 支持两种注入方式：

- `.Values.extraEnvFromSecret`：把同一个 Kubernetes Secret 注入到所有后端 deployment，包括 API、webserver、Celery、bot、MCP 等。
- 各 workload 的 `extraEnv`：只给指定 deployment 注入变量，例如 `api.extraEnv`、`celery_worker_primary.extraEnv`。

最少配置可以创建一个 Secret：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: onyx-langfuse-tracing
type: Opaque
stringData:
  LANGFUSE_PUBLIC_KEY: pk-lf-...
  LANGFUSE_SECRET_KEY: sk-lf-...
```

然后在 values 中配置：

```yaml
extraEnvFromSecret: onyx-langfuse-tracing

configMap:
  LANGFUSE_HOST: "https://onyx.yourcompany.com/observability"
  TRACING_MASKING_LENGTH: "100000"
```

这个方式落地最快，但不是最小权限，因为 `extraEnvFromSecret` 会注入到 webserver 等不需要 Langfuse secret 的后端 pod。如果生产要求严格最小权限，改用 per-workload `extraEnv`，至少覆盖：

```yaml
api:
  extraEnv:
    - name: LANGFUSE_PUBLIC_KEY
      valueFrom:
        secretKeyRef:
          name: onyx-langfuse-tracing
          key: LANGFUSE_PUBLIC_KEY
    - name: LANGFUSE_SECRET_KEY
      valueFrom:
        secretKeyRef:
          name: onyx-langfuse-tracing
          key: LANGFUSE_SECRET_KEY

celery_worker_primary:
  extraEnv:
    - name: LANGFUSE_PUBLIC_KEY
      valueFrom:
        secretKeyRef:
          name: onyx-langfuse-tracing
          key: LANGFUSE_PUBLIC_KEY
    - name: LANGFUSE_SECRET_KEY
      valueFrom:
        secretKeyRef:
          name: onyx-langfuse-tracing
          key: LANGFUSE_SECRET_KEY
```

同样的 `extraEnv` 需要重复到：

- `celery_worker_docfetching`
- `celery_worker_docprocessing`
- `celery_worker_light`
- `celery_worker_heavy`
- `celery_worker_monitoring`
- `celery_worker_user_file_processing`
- `celery_worker_scheduled_tasks`，如果启用且会调用 LLM
- `slackbot` / `discordbot` / `mcpServer`，如果对应进程会调用 LLM

Helm 中不要把 `LANGFUSE_SECRET_KEY` 放进 `configMap`。如果前端入口用 `NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH`，可以放到 `configMap`，但当前 Next.js client-side public env 通常在构建时固化；需要同步更新 `web/Dockerfile` 的 `ARG` / `ENV` 并重建 web 镜像，或改成由服务端 runtime settings API 提供入口路径。

### 9.3 不要重复埋点

不要在业务代码中新增这种分散式 Langfuse SDK 调用：

```python
from langfuse.decorators import observe

@observe()
def process_chat_message(...):
    ...
```

也不要在 `process_message.py` 或 `llm_loop.py` 里直接手写：

```python
trace = langfuse.trace(...)
with trace.generation(...):
    ...
```

这样会绕过 Onyx 的 trace framework、`LLMFlow`、脱敏、usage/cost 记录和多 provider processor。

也不要为了 Langfuse 单独新增第二套 tracing abstraction、decorator 或 request middleware。Onyx 现在的设计是一个 trace framework 可以同时挂多个 processor，例如 Braintrust 和 Langfuse。新增 provider 应该接入 `TracingProcessor`，新增业务调用应该补 Onyx span。

正确方式：

```python
from onyx.tracing.flows import LLMFlow
from onyx.tracing.framework.create import ensure_trace
from onyx.tracing.llm_utils import llm_generation_span
from onyx.tracing.llm_utils import record_llm_response

with ensure_trace(
    "chat_session_naming",
    group_id=str(chat_session_id),
    metadata={
        "tenant_id": tenant_id,
        "chat_session_id": str(chat_session_id),
        "user_id": str(user_id),
    },
):
    with llm_generation_span(
        llm=llm,
        flow=LLMFlow.CHAT_SESSION_NAMING,
        input_messages=messages,
    ) as span:
        response = llm.invoke(messages)
        record_llm_response(span, response)
```

对于绕过 `LLM` 抽象的 direct provider SDK、LiteLLM、model_server HTTP、embedding、rerank、image、voice 调用，使用：

```python
from onyx.tracing.flows import LLMFlow
from onyx.tracing.llm_utils import traced_llm_call

with traced_llm_call(
    flow=LLMFlow.RERANK,
    model=model_name,
    provider=provider_name,
    input_messages=request_payload,
) as span:
    result = call_model_server(...)
    span.span_data.output = [{"result_count": len(result)}]
    span.span_data.usage = usage
```

### 9.4 `LLMFlow` 规范

- `LLMFlow` 表示业务操作，例如 `chat_response`、`image_summarization`、`rerank`，不是 provider 名称。
- 新增模型相关操作时，先在 `backend/onyx/tracing/flows.py` 添加 enum。
- 不要传裸字符串 flow。
- Langfuse dashboard 中如果出现大量 `untagged_invoke` 或 `untagged_stream`，说明需要回到调用点补明确 `LLMFlow`。

### 9.5 Trace coverage 检查点

上线前至少检查这些高价值路径是否会进入 Langfuse：

| Onyx 能力 | 典型入口 | 期望 trace / flow |
| --- | --- | --- |
| Chat response | 普通聊天 | `run_llm_loop` trace，`chat_response` generation |
| Session naming | 新会话命名 | `chat_session_naming` trace，`chat_session_naming` generation |
| History compression | 长对话压缩 | `chat_history_compression` trace，`chat_history_summarization` generation |
| Contextual RAG | 文档处理 / indexing | `contextual_rag_doc_summary`、`contextual_rag_chunk_context` |
| Image summarization | 文件处理 | `image_summarization` |
| Embedding | model server boundary | `embed_query`、`embed_passage` |
| Rerank | 搜索结果重排 | `rerank` |
| Intent classification | 搜索/聊天意图判断 | `intent_classification` |
| Voice | STT/TTS | `stt`、`tts` |
| Image generation/edit | 图像能力 | `image_generation`、`image_edit` |

如果这些路径没有 trace，先确认调用点是否被 `ensure_trace(...)` 包住，再确认 generation span 是否用了 `LLMFlow`。对于 Celery task，代码变更后需要重启对应 worker。

### 9.6 运行时性能和失败语义

Onyx 的 trace processor 是同步接收 trace/span start/end 事件的，但 Langfuse SDK 本身通常异步批量发送数据。当前代码在 processor 内部捕获并记录异常，不会因为 Langfuse 上报失败中断用户请求或 worker task。

生产上需要关注：

- Langfuse SDK 队列积压会增加内存压力。
- ClickHouse、Redis、S3 不可用时，Langfuse web/worker 可能正常启动但 ingestion 延迟或失败。
- `force_flush()` / `shutdown()` 已在 processor 中实现，但 API server 是否优雅 shutdown、Celery worker 是否有足够退出时间，仍取决于部署环境。
- 高流量 indexing / docprocessing 会产生大量 generation spans，尤其 contextual RAG 和 image summarization。需要控制 Langfuse retention、ClickHouse 存储、采样或 feature 开关。
- 当前 `setup_tracing()` 是幂等的进程内初始化。如果在同一进程里修改 `LANGFUSE_*` 环境变量，不会自动重新初始化 provider，必须重启进程。

建议为 Langfuse stack 自身接入基础监控：

- Langfuse web/worker container restart count。
- ClickHouse disk usage、query latency、insert error。
- Redis memory 和 queue length。
- S3/MinIO upload error。
- Onyx 日志中 `Error starting Langfuse span`、`Error ending Langfuse span`、`Failed to flush Langfuse client`。

---

## 10. Onyx 前端入口

目标是在 Onyx 管理后台提供 “Observability” 入口，但不要用 iframe。

推荐位置：

- 路由配置：`web/src/lib/admin-routes.ts`
- 管理后台 sidebar：`web/src/sections/sidebar/AdminSidebar.tsx`

建议新增一个只对 admin 可见的外部入口：

```ts
OBSERVABILITY: {
  path: "/observability",
  icon: SvgActivity,
  title: "Observability",
  sidebarLabel: "Observability",
}
```

在 sidebar 渲染时使用普通 anchor 或让现有 `SidebarTab` 走完整页面跳转。不要依赖 Next.js client routing 去处理 `/observability`，因为该路径由反向代理交给 Langfuse，不是 Onyx Next.js route。

建议将入口放在 Usage section：

```ts
if (!isCurator) {
  addGated(SECTIONS.USAGE, ADMIN_ROUTES.USAGE, Tier.BUSINESS);
  add(SECTIONS.USAGE, ADMIN_ROUTES.OBSERVABILITY);
}
```

更稳妥的生产实现是加一个前端公开配置，例如：

```env
NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH=/observability
```

只有该变量非空时才显示入口。这样没有部署 Langfuse 的环境不会出现无效菜单。

实现时还需要在 `web/Dockerfile` 的 builder 和 runner 阶段声明同名 `ARG` / `ENV`，并在 `deployment/docker_compose/docker-compose.yml` 或镜像构建流水线中传入 build arg。否则 `process.env.NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH` 在已构建的前端 bundle 中可能为空。

安全边界：

- 前端入口只改善体验，不负责授权。
- Langfuse 访问必须由 Langfuse/IdP 自己控制。
- 如果只想让 Onyx admins 访问 Langfuse，需要把 Onyx admin group 同步到 IdP，或在 IdP 的 `langfuse-app` client 上做 group/policy 限制。

---

## 11. 可选：Onyx 原生 Dashboard 监控卡片

可以在 Onyx admin dashboard 展示 Langfuse 汇总指标，例如今日 traces、失败率、平均 latency、token cost。

不要从浏览器直接调用 Langfuse Public API，也不要把 Langfuse secret 放进 `NEXT_PUBLIC_*`。推荐做法：

1. 后端新增 Onyx admin-only API。
2. 后端使用 Langfuse API key server-to-server 查询。
3. 前端只调用 Onyx API。

后端实现要求：

- 遵守 Onyx FastAPI 规范，新 API 不使用 `response_model`。
- 错误处理用 `OnyxError`，不要直接抛 `HTTPException`。
- Langfuse API secret 只从后端环境变量读取。
- 对返回数据做最小化，避免把 prompt/input/output 透传到 dashboard 卡片。

---

## 12. 测试流程

### 12.1 部署和路由

1. 启动 Onyx、Langfuse、IdP。
2. 访问 `https://onyx.yourcompany.com/`，确认 Onyx 正常。
3. 访问 `https://onyx.yourcompany.com/observability/`，确认进入 Langfuse。
4. 打开浏览器 network，确认静态资源从 `/observability/_next/...` 加载且没有 404。
5. 访问 `https://onyx.yourcompany.com/observability/api/auth/signin`，确认 Langfuse auth route 正常。

### 12.2 OIDC 登录

1. 从 Onyx 登录页走 OIDC 登录，回调应落到 `/auth/oidc/callback`。
2. 从 Langfuse 登录页走 Keycloak 登录，回调应落到 `/observability/api/auth/callback/keycloak`。
3. 如果用户已在 IdP 登录，访问 Langfuse 时应只发生短暂 redirect，或无需再次输入密码。
4. 用不在授权 group 的用户访问 Langfuse，确认被 IdP 或 Langfuse 拒绝。

### 12.3 Onyx tracing

1. 在 Langfuse 创建 project 并复制 key。
2. 在 Onyx API server 和所有 Celery worker 配置 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_HOST`。
3. 重启 Onyx API server 和相关 Celery worker。Celery worker 没有代码热重载。
4. 在 Onyx 发起一次普通 chat。
5. 触发一次 session naming 或 chat history compression。
6. 如果要验证后台 worker，触发一次会调用模型的文档处理、图片总结或 contextual RAG。
7. 在 Langfuse 中确认出现 trace：
   - trace name 如 `run_llm_loop`、`chat_session_naming`。
   - user/session 字段可见。
   - generation observation 有 model、usage、cost。
   - metadata 中有 `tenant_id`、`chat_session_id` 等业务字段。
8. 检查 Langfuse 中是否出现 `untagged_invoke` / `untagged_stream`，如有则回到对应调用点补 `LLMFlow`。

### 12.4 日志

Onyx 服务日志：

```text
backend/log/api_server_debug.log
backend/log/celery_primary_debug.log
backend/log/celery_docprocessing_debug.log
backend/log/celery_docfetching_debug.log
```

Langfuse 容器日志：

```bash
docker logs -f langfuse-web
docker logs -f langfuse-worker
```

期望看到：

- Onyx 日志中有 `Tracing initialized with providers: langfuse`。
- Langfuse web ready。
- Langfuse worker 正常消费事件，无 ClickHouse/Redis/S3 连接错误。

### 12.5 验收标准

部署验收：

- `/observability/` 首屏可打开，无静态资源 404。
- `/observability/api/auth/signin` 可进入 Langfuse 登录流程。
- Onyx OIDC 和 Langfuse OIDC 分别能完成登录回调。
- 未授权用户不能访问 Langfuse project。

Tracing 验收：

- Onyx API server 启动日志显示 Langfuse tracing 初始化成功。
- 至少一次 chat trace 能在 Langfuse 中看到 `user_id`、`session_id`、`tenant_id`。
- 至少一个 generation observation 有 `model`、input/output、token usage。
- 至少一个 worker 触发的模型调用能在 Langfuse 中看到。
- `untagged_invoke` / `untagged_stream` 不作为正常状态长期存在；如果存在，必须有明确调用点和修复计划。
- 随机抽查一个 trace，确认 root observation 的 input/output 来自 first input / last output，符合预期且没有误导分析。
- 随机抽查一个带 reasoning 的 generation，确认 reasoning metadata 的可见范围符合数据策略。

安全验收：

- 浏览器构建产物和 network 请求中没有 `LANGFUSE_SECRET_KEY`。
- Langfuse project key 不写入 git、前端代码或公开配置。
- Langfuse UI 中敏感 prompt/output 的可见范围符合内部数据策略。
- Langfuse/IdP 侧有独立授权策略，不能只依赖 Onyx 菜单入口隐藏。
- `TRACING_MASKING_LENGTH` 和 masking 规则已按生产数据策略评审。
- 多租户场景下，Langfuse project 权限和 `tenant_id` metadata 策略已经明确。

### 12.6 测试矩阵

| 测试域 | 场景 | 执行方式 | 通过标准 |
| --- | --- | --- | --- |
| 子路径路由 | `/observability/` 首屏和刷新 | 浏览器访问并刷新 Langfuse trace/detail/settings 页面 | 页面可打开，刷新不落回 Onyx 404。 |
| 静态资源 | Next.js assets | 浏览器 network 检查 `/observability/_next/...` | 无 404，无被代理 rewrite 到根路径的资源。 |
| Auth callback | Langfuse Keycloak 登录 | 从 Langfuse 登录页发起 OIDC | redirect URI 为 `/observability/api/auth/callback/keycloak`，登录后回到 Langfuse。 |
| Onyx OIDC | Onyx 登录 | 从 Onyx 登录页发起 OIDC | callback 为 `/auth/oidc/callback`，Onyx session 正常创建。 |
| SSO 体验 | 先登录 Onyx，再访问 Langfuse | 同一浏览器打开 `/observability` | 用户不需要再次输入密码，或只经历 IdP 的短重定向。 |
| 授权 | 非观测用户访问 Langfuse | 使用不在 Langfuse 授权 group 的用户 | IdP 或 Langfuse 拒绝访问。 |
| API trace | 普通 chat | Onyx UI 发起一次 chat | Langfuse 出现 `run_llm_loop` trace 和 `chat_response` generation。 |
| Session metadata | chat session | 检查 Langfuse trace facets | `user_id`、`session_id`、`tenant_id` 可筛选或在 metadata 可见。 |
| Worker trace | 文档处理 / contextual RAG / image summary | 触发一次 worker 内模型调用 | Langfuse 能看到来自 worker 的 generation，不只 API server 有 trace。 |
| Usage/cost | 生成类调用 | 检查 generation observation | model、token usage 存在；可识别模型时 cost 存在。 |
| `LLMFlow` | 新增或高价值路径 | 搜索 Langfuse 中 `untagged_invoke` / `untagged_stream` | 不作为正常状态长期存在。 |
| Masking | 带 authorization/private_key 的输入 | 发起测试请求或单元测试 masking | Langfuse 中敏感字段被 `***REDACTED***` 替代，超长内容被截断。 |
| Secret 暴露 | 前端 bundle/network | 浏览器 devtools 或构建产物搜索 | 没有 `LANGFUSE_SECRET_KEY`、Langfuse Basic Auth token 或 project secret。 |
| 滚动发布 | API/worker 重启 | 触发 trace 后滚动重启 | 主流程不中断；尾部 trace 丢失在可接受范围，或 flush 逻辑已验证。 |
| 故障降级 | Langfuse 临时不可用 | 停止 Langfuse worker 或阻断 host | Onyx 用户请求不失败；日志有 tracing 错误但业务继续。 |

---

## 13. 生产落地步骤

推荐分阶段上线：

### Phase 1：独立部署 Langfuse

- 按官方 compose/Helm 部署 Langfuse v3。
- 先使用独立子域名验证基础功能，例如 `https://langfuse.yourcompany.com`。
- 创建 project、验证 API key、验证 ClickHouse/Redis/S3。

### Phase 2：切到 Onyx 同域子路径

- 构建带 `NEXT_PUBLIC_BASE_PATH=/observability` 的 `langfuse-web` 镜像。
- 更新 `NEXTAUTH_URL=https://onyx.yourcompany.com/observability/api/auth`。
- 配置反向代理，不剥离 `/observability`。
- 更新 IdP callback URL。
- 验证 UI、静态资源、auth callback。

如果团队不想维护自定义 Langfuse web 镜像，生产上可以退而求其次使用独立子域名。独立子域名不会有 base path 静态资源问题，稳定性更高，但不满足“同域子路径”的体验目标。

### Phase 3：启用 Onyx tracing

- 给 API server 和所有 workers 配置 Langfuse key。
- 重启服务。
- 验证 chat、worker、image/voice/rerank/embedding 等模型调用。
- 清理 `UNTAGGED_*`。

### Phase 4：前端入口和可选 dashboard

- 添加 admin sidebar 入口。
- 可选实现后端代理汇总指标。
- 对访问权限做 IdP group policy 验证。

### 13.1 代码和配置变更清单

后端代码通常无需新增 Langfuse SDK 埋点，但可能需要：

- 检查 `backend/onyx/tracing/langfuse_tracing_processor.py` 与目标 Langfuse SDK/platform 版本兼容。
- 对出现 `UNTAGGED_*` 的调用点补 `LLMFlow` 和 `llm_generation_span` / `traced_llm_call`。
- 如果新增 dashboard 汇总 API，在 `backend/onyx/server/...` 下实现 admin-only API，错误处理用 `OnyxError`。
- 如果新增 DB 存储，所有 DB 操作放在 `backend/onyx/db` 或 `backend/ee/onyx/db`。

前端代码可能需要：

- `web/src/lib/admin-routes.ts` 增加 `OBSERVABILITY` route。
- `web/src/sections/sidebar/AdminSidebar.tsx` 按 `NEXT_PUBLIC_LANGFUSE_OBSERVABILITY_PATH` 决定是否显示入口。
- 确保跳转使用完整页面导航，避免 Next.js 把 `/observability` 当作 Onyx app route。

部署配置需要：

- Langfuse web 自构建镜像。
- Langfuse worker、Postgres、ClickHouse、Redis、S3/MinIO。
- Onyx API server 和所有 worker 的 `LANGFUSE_*`。
- IdP 两个 client：`onyx-app`、`langfuse-app`。
- 反向代理 `/observability` path。

### 13.2 PR 拆分建议

如果需要把方案变成代码和部署变更，建议拆成小 PR，避免把可观测性、SSO、前端入口和数据治理混在一起：

| PR | 范围 | 主要内容 | 验证重点 |
| --- | --- | --- | --- |
| PR 1 | 文档和部署样例 | 本方案文档、compose/Helm values 示例、反向代理示例 | 配置变量和服务名与仓库一致。 |
| PR 2 | Onyx tracing 配置落地 | 在部署文件中注入 `LANGFUSE_*`，必要时补 `LANGFUSE_BASE_URL` alias | API server 和 worker 启动日志显示 Langfuse provider。 |
| PR 3 | 前端入口 | admin sidebar 增加 Observability 外部跳转，并由公开配置控制显示 | 无 Langfuse 部署时入口隐藏；点击后完整页面跳转。 |
| PR 4 | Trace coverage 修补 | 清理高价值路径的 `UNTAGGED_*`，新增缺失 `LLMFlow` | Chat、worker、embedding/rerank/image/voice 路径都有明确 flow。 |
| PR 5 | 生产数据治理 | masking 规则、input/output 开关、采样或 truncation 配置 | 敏感字段不会进入 Langfuse，usage/cost 仍可见。 |
| PR 6 | Shutdown flush | API lifespan 和 Celery shutdown 调用 trace provider flush/shutdown | 滚动发布时尾部 trace 丢失明显减少。 |
| PR 7 | 可选 dashboard | Onyx admin-only API 查询 Langfuse 汇总指标，前端展示卡片 | 不暴露 prompt/input/output 和 Langfuse secret。 |

首版上线不一定需要 PR 4-7。最低可行范围是部署 Langfuse、配置 Onyx `LANGFUSE_*`、验证 API/worker trace、加前端入口。

### 13.3 回滚方式

这不是数据库 schema 改造型集成，回滚应优先通过配置完成：

1. 从 Onyx API server 和 workers 移除 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`，重启服务，停止上报 trace。
2. 从 Onyx sidebar 隐藏 `/observability` 入口。
3. 保留 Langfuse 服务用于历史数据查看；确认不再需要后再下线 Langfuse stack。
4. 如果反向代理变更导致 Onyx 主站异常，先移除 `/observability` location，保留 `/` 到 Onyx 的路由。

回滚不需要修改 Onyx 业务数据库。

---

## 14. 运维 Runbook

### 14.1 正常运行信号

Onyx 侧：

- API server 和 worker 启动日志出现 `Tracing initialized with providers: langfuse`。
- 没有持续出现 `Error starting Langfuse span`、`Error ending Langfuse span`、`Failed to flush Langfuse client`。
- Chat、worker、embedding/rerank 等路径在 Langfuse 中都能看到新 trace。

Langfuse 侧：

- `langfuse-web` ready。
- `langfuse-worker` 持续消费事件，无 ClickHouse insert error。
- ClickHouse 磁盘、Redis 内存、对象存储上传错误率处于正常范围。
- Langfuse UI 中 trace 延迟可接受，例如用户操作后几十秒内可见。

### 14.2 常用排查命令

Onyx 日志：

```bash
tail -n 200 backend/log/api_server_debug.log
tail -n 200 backend/log/celery_docprocessing_debug.log
tail -n 200 backend/log/celery_docfetching_debug.log
```

Langfuse 容器：

```bash
docker logs --tail 200 langfuse-web
docker logs --tail 200 langfuse-worker
```

如果使用 docker compose，可先确认核心服务健康：

```bash
docker compose ps langfuse-web langfuse-worker clickhouse redis postgres
```

### 14.3 Trace 丢失排查顺序

1. 确认对应 Onyx 进程有 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_HOST`。
2. 确认进程已重启。`setup_tracing()` 是进程内幂等初始化，运行中修改环境变量不会生效。
3. 查 Onyx 日志是否初始化 Langfuse provider。
4. 查调用点是否在 active trace 内。没有 active trace 时会返回 `NoOpSpan`。
5. 查调用点是否记录 output/usage，例如是否调用 `record_llm_response(...)`。
6. 查 Langfuse worker 是否积压或 ClickHouse 是否写入失败。
7. 查是否写到了另一个 Langfuse project 或另一个 environment。

### 14.4 滚动发布注意事项

当前 `LangfuseTracingProcessor` 实现了 `force_flush()` 和 `shutdown()`，但需要由 trace provider shutdown 路径触发。上线前建议补充并验证：

- API server lifespan shutdown 中调用 trace provider shutdown 或 force flush。
- Celery `worker_shutdown` 中调用 trace provider shutdown 或 force flush。
- Kubernetes `terminationGracePeriodSeconds` 足够让 Langfuse SDK flush 完成。
- 短生命周期命令，例如 eval CLI、一次性 worker、migration 脚本，如果启用了 tracing，应在退出前显式 flush。

如果暂时不改代码，应接受滚动发布时尾部少量 trace 可能丢失，并在验收中重点验证长生命周期 API/worker 的主要 trace。

### 14.5 存储和保留策略

Langfuse trace 数据增长很快，尤其 indexing 和 contextual RAG 会写入大量 prompt/context/output。生产需要明确：

- ClickHouse retention。
- Postgres backup 和 restore。
- S3/MinIO bucket lifecycle。
- 大 trace 的采样或功能级开关。
- 是否区分 dev/staging/prod project。
- 是否为高吞吐 worker 单独设置上报策略，例如只保留 usage/cost/latency，不保留完整 input/output。

### 14.6 事故处理

Langfuse 不应成为 Onyx 主业务链路的硬依赖。出现 Langfuse 故障时：

1. 先确认 Onyx 用户请求是否正常。如果正常，按可观测性降级处理。
2. 如果 Langfuse SDK 队列导致 Onyx 内存或延迟异常，优先从 Onyx 服务移除 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 并重启，停止上报。
3. 保留 `LANGFUSE_HOST` 无法单独禁用上报；当前初始化条件是 public key + secret key。
4. Langfuse stack 恢复后，再逐个恢复 worker 和 API server 的 key。
5. 恢复后抽查新的 trace，不要假设故障期间的 trace 会自动补齐。

---

## 15. 后续工程增强项

这些增强不是首版上线必需，但建议排进后续迭代：

1. 在 `backend/onyx/tracing/setup.py` 支持 `LANGFUSE_BASE_URL` 作为 `LANGFUSE_HOST` 的别名，减少和官方 SDK 文档的认知差异。
2. 在 API server lifespan 和 Celery shutdown 路径显式调用 trace provider shutdown/flush，降低滚动发布时的尾部 trace 丢失。
3. 增加 `LANGFUSE_TRACE_INPUT_OUTPUT_ENABLED` 或类似开关，允许生产只上报 metadata、usage、cost、latency。
4. 扩展 `backend/onyx/tracing/masking.py`，增加项目需要的 secret/PII 规则，并给 masking 写单元测试。
5. 让 `LangfuseTracingProcessor` 把 `LLMFlow` 放到更易筛选的 Langfuse metadata 字段，例如 generation observation metadata 中的 `flow`。
6. 为 `UNTAGGED_INVOKE` / `UNTAGGED_STREAM` 增加定期检查或 CI 搜索，避免新调用长期缺少业务 flow。
7. 为 Langfuse project key 增加部署级轮换流程。
8. 如果确实需要 tenant 硬隔离，设计进程级 tenant-to-project 映射，而不是在调用点动态切换全局 Langfuse client。

---

## 16. 常见问题

### 16.1 `/observability` 能打开，但静态资源 404

检查：

- `langfuse-web` 是否用 `--build-arg NEXT_PUBLIC_BASE_PATH=/observability` 从源码构建。
- 运行时是否设置 `NEXT_PUBLIC_BASE_PATH=/observability`。
- Nginx/Ingress 是否剥离了 `/observability` 前缀。
- Helm readiness/liveness probe 是否包含 base path。

### 16.2 Langfuse OIDC redirect URI mismatch

Keycloak client `langfuse-app` 应包含：

```text
https://onyx.yourcompany.com/observability/api/auth/callback/keycloak
```

如果使用 custom provider，则是：

```text
https://onyx.yourcompany.com/observability/api/auth/callback/custom
```

### 16.3 Onyx OIDC 登录失败

检查 Onyx 变量名：

```env
AUTH_TYPE=oidc
OPENID_CONFIG_URL=...
OAUTH_CLIENT_ID=...
OAUTH_CLIENT_SECRET=...
WEB_DOMAIN=https://onyx.yourcompany.com
```

Onyx callback 是：

```text
https://onyx.yourcompany.com/auth/oidc/callback
```

### 16.4 Onyx 没有 trace 进入 Langfuse

检查：

- `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY` 是否配置在实际产生调用的进程里。
- `LANGFUSE_HOST` 是否包含 `/observability`。
- 是否误配成只有 `LANGFUSE_BASE_URL`，但当前 Onyx 代码读取的是 `LANGFUSE_HOST`。
- Onyx 服务是否重启。
- 日志是否有 `Tracing initialized with providers: langfuse`。
- 调用点是否处于 active trace 中。没有 root trace 时 generation span 会变成 NoOp。
- 是否把 trace 写到了另一个 Langfuse project。

### 16.5 Langfuse 中出现 orphan span

可能原因：

- span 创建时没有 active trace。
- 多线程场景 parent trace/span ID 没有正确传递。
- 业务代码绕过了 Onyx tracing framework，直接用了 Langfuse SDK。

优先修复调用点，使用 `ensure_trace(...)` 包住完整业务流程。

### 16.6 用户仍然看到两套登录页面

这是正常现象。Onyx 和 Langfuse 是两个应用，各自维护 session。统一的是 IdP 登录态，不是应用 session cookie。只要 IdP session 仍有效，用户进入另一应用时通常无需再次输入密码。

### 16.7 Langfuse 中 trace user/session 为空

检查创建 trace 时 metadata 是否包含：

```python
metadata={
    "user_id": str(user_id),
    "chat_session_id": str(chat_session_id),
    "tenant_id": tenant_id,
}
```

当前 processor 只把 `user_id` 和 `chat_session_id` 提升为 Langfuse 一等字段。`group_id` 不会自动变成 Langfuse session。

### 16.8 Usage/cost 缺失

检查：

- 调用点是否调用了 `record_llm_response(...)` 或 `record_llm_span_output(...)`。
- direct SDK/model_server 调用是否手动设置了 `span.span_data.usage`。
- usage key 是否是 `prompt_tokens` / `completion_tokens` 或 `input_tokens` / `output_tokens`。
- `data.model` 是否能被 `onyx.llm.cost.calculate_llm_cost_cents` 识别。无法识别模型时 token usage 仍可出现，但 cost 可能为空。

---

## 17. 实施检查清单

- [ ] 确认是否必须同域子路径。如果不是，优先考虑独立子域名降低维护成本。
- [ ] Langfuse web 镜像已用 `/observability` base path 构建。
- [ ] `NEXTAUTH_URL` 设置为 `https://onyx.yourcompany.com/observability/api/auth`。
- [ ] 反向代理没有 rewrite 掉 `/observability`。
- [ ] Keycloak 有 `onyx-app` 和 `langfuse-app` 两个 client。
- [ ] Onyx OIDC callback 是 `/auth/oidc/callback`。
- [ ] Langfuse Keycloak callback 是 `/observability/api/auth/callback/keycloak`。
- [ ] Onyx API server 和所有 Celery worker 都有 `LANGFUSE_*` 环境变量。
- [ ] Langfuse project key 没有进入前端。
- [ ] Langfuse 访问权限由 IdP/Langfuse 控制，不只依赖 Onyx 菜单隐藏。
- [ ] Chat trace、worker trace、usage/cost、user/session metadata 已验证。
- [ ] Langfuse dashboard 中 `UNTAGGED_INVOKE` / `UNTAGGED_STREAM` 已清理或有明确跟进项。
- [ ] API / Celery shutdown flush 策略已确认，或已接受滚动发布时尾部 trace 可能丢失。
- [ ] Langfuse retention、备份、bucket lifecycle、ClickHouse 容量告警已配置。

---

## 18. 参考

- Langfuse Docker Compose 部署文档：https://langfuse.com/self-hosting/deployment/docker-compose
- Langfuse Custom Base Path 文档：https://langfuse.com/self-hosting/configuration/custom-base-path
- Langfuse Authentication and SSO 文档：https://langfuse.com/self-hosting/security/authentication-and-sso
- Langfuse SDK 概览：https://langfuse.com/docs/observability/sdk/overview
- Onyx tracing processor：`backend/onyx/tracing/langfuse_tracing_processor.py`
- Onyx tracing setup：`backend/onyx/tracing/setup.py`
- Onyx LLM tracing helpers：`backend/onyx/tracing/llm_utils.py`
- Onyx LLMFlow registry：`backend/onyx/tracing/flows.py`
