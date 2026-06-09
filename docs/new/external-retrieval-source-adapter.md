# 外部检索源适配器开发方案

## 1. 背景与目标

当前希望将 ontology 作为外部检索源接入 Onyx。前期 ontology 服务和数据结构不一定稳定，因此不适合一开始同步到 Vespa / OpenSearch 主索引，也不适合作为普通 connector 长周期索引。更合适的第一阶段方案是建设一个独立的外部检索源适配器层：

```text
Chat / Search query
  -> Onyx search tool
  -> Internal Vespa / OpenSearch retrieval
  -> External Retrieval Source Adapter
  -> Normalized InferenceChunk
  -> RRF / rerank / LLM answer
```

目标：

1. 支持 ontology 这类不稳定外部源以 HTTP endpoint 方式接入。
2. 定义统一、全面的检索结果字段协议。
3. 当外部源没有返回统一字段时，按降级规则从简单字段中提取必要信息。
4. 当必要字段无法得到时，在测试和配置阶段明确报错；运行时检索默认 fail-open，不阻断主检索。
5. 独立建设 admin 菜单和配置页面，让接入、测试、启停、降级都可控。
6. 支持后续接入更多外部检索源，而不是只为 ontology 写一次性逻辑。

非目标：

1. 不在 MVP 阶段把 ontology 全量同步到 Vespa / OpenSearch。
2. 不让外部源绕过 Onyx 现有 ACL、document set、persona、source filter 和租户隔离。
3. 不把外部源结果的可信度完全交给 LLM 判断。
4. 不在实时链路默认使用 embedding 去重。

## 2. 当前项目可复用能力

当前 Onyx 已有 `backend/onyx/federated_connectors` 和 `/federated` API，Slack federated search 已经走“查询时实时检索外部系统，再转为 `InferenceChunk`”的路径。

可复用点：

1. `InferenceChunk` / `InferenceSection` 作为最终检索结果统一模型。
2. document set 可以绑定 federated connector 的思路。
3. `SearchTool` 中并行执行内部检索和外部检索，再做 weighted RRF 的思路。
4. 加密凭证、租户 DB session、admin 权限、SWR fetch、SettingsLayouts 页面结构。

不建议直接复用的点：

1. 现有 `FederatedConnector` 接口强依赖 OAuth 语义，例如 `authorize` / `callback`。
2. 当前通用 federated retrieval 可能会随 query expansion 被多次调用；ontology 这类外部源默认不应该被放大调用。
3. 现有 `/admin/federated/[id]` 页面更像 connector 编辑页，不适合承载多种 HTTP adapter 的映射、测试、预览、降级配置。

建议新增独立能力层：`External Retrieval Sources`。

## 3. 推荐架构

### 3.1 后端模块

新增模块：

```text
backend/onyx/external_retrieval/
  __init__.py
  adapters/
    __init__.py
    base.py
    http_json.py
    ontology.py
  normalization.py
  dedupe.py
  errors.py
  models.py
  registry.py
  retrieval.py

backend/onyx/server/external_retrieval/
  __init__.py
  api.py
  models.py

backend/onyx/db/external_retrieval.py
```

DB 操作必须放在 `backend/onyx/db/external_retrieval.py`。如果后续有 EE 扩展，则放在 `backend/ee/onyx/db` 对应目录。

### 3.2 前端模块

新增 admin 独立菜单：

```text
web/src/app/admin/external-retrieval/page.tsx
web/src/app/admin/external-retrieval/new/page.tsx
web/src/app/admin/external-retrieval/[id]/page.tsx
web/src/app/admin/external-retrieval/[id]/test/page.tsx
web/src/app/admin/external-retrieval/lib.ts
web/src/app/admin/external-retrieval/types.ts
```

同时在 `web/src/lib/admin-routes.ts` 增加：

```text
EXTERNAL_RETRIEVAL_SOURCES
  path: /admin/external-retrieval
  title: External Retrieval Sources
  sidebarLabel: External Retrieval
```

前端必须遵守桌面 Web 范围，使用 Opal / refresh components：

1. 新页面使用 `SettingsLayouts.Root` / `SettingsLayouts.Header` / `SettingsLayouts.Body`。
2. 文本使用 Opal `Text` 或 refresh `Text`，不要裸 `<p>` / `<h1>` / `<span>`。
3. 按钮使用 Opal `Button`。
4. 图标使用 `@opal/icons` 或 `web/src/icons`，不要使用 lucide/react-icons。
5. 仅做桌面布局，默认验证 1440px 宽，覆盖 1200px 到 1920px。

## 4. 外部源统一协议

### 4.1 请求协议

Onyx 调用外部源时，标准请求体建议为：

```json
{
  "schema_version": "1.0",
  "query": "用户原始问题或主检索问题",
  "limit": 10,
  "filters": {
    "document_sets": ["Engineering KB"],
    "source_types": ["external_retrieval"],
    "time_range": {
      "start": "2026-01-01T00:00:00Z",
      "end": null
    },
    "namespaces": ["engineering"],
    "entity_types": ["Component", "Issue"],
    "relation_types": ["caused_by", "depends_on"]
  },
  "options": {
    "max_hops": 2,
    "min_confidence": 0.65,
    "include_paths": true,
    "include_raw_graph": false
  },
  "context": {
    "tenant_id": "tenant-id",
    "user_id": "user-id",
    "request_id": "request-id"
  }
}
```

MVP 阶段允许外部源只支持：

```json
{
  "query": "用户问题",
  "limit": 10
}
```

是否发送完整请求由 admin 配置决定：

```text
request_mode = standard | simple | custom_template
```

### 4.2 响应协议

推荐完整响应：

```json
{
  "schema_version": "1.0",
  "request_id": "external-request-id",
  "results": [
    {
      "result_id": "ontology:fact:123",
      "canonical_key": "component:battery_management_system",
      "fact_key": "component:battery_management_system|caused_by|issue:thermal_runaway",
      "title": "Battery Management System failure causes",
      "content": "The battery management system failure is commonly linked to thermal runaway under ...",
      "summary": "A concise summary suitable for citations.",
      "url": "https://example.com/articles/bms-failure",
      "score": 0.82,
      "confidence": 0.74,
      "updated_at": "2026-05-20T10:00:00Z",
      "source": {
        "type": "ontology",
        "name": "Engineering Ontology",
        "source_id": "article-789"
      },
      "entity": {
        "id": "component-bms",
        "type": "Component",
        "name": "Battery Management System"
      },
      "relations": [
        {
          "subject": "Battery Management System",
          "predicate": "caused_by",
          "object": "thermal runaway",
          "confidence": 0.71
        }
      ],
      "paths": [
        {
          "nodes": ["Battery Management System", "thermal runaway"],
          "edges": ["caused_by"],
          "hop_count": 1,
          "score": 0.71
        }
      ],
      "provenance": [
        {
          "source_id": "JIRA-123",
          "source_type": "jira",
          "title": "Battery failure analysis",
          "url": "https://jira.example.com/browse/JIRA-123",
          "updated_at": "2026-05-18T08:00:00Z"
        }
      ],
      "metadata": {
        "namespace": "engineering",
        "ontology_version": "v0.3.1"
      }
    }
  ],
  "warnings": [],
  "diagnostics": {
    "latency_ms": 120,
    "retrieval_mode": "hybrid_graph_article"
  }
}
```

MVP 响应允许简化为：

```json
{
  "results": [
    {
      "title": "Battery failure analysis",
      "content": "Article text or evidence snippet...",
      "confidence": 0.82,
      "url": "https://example.com/articles/bms"
    }
  ]
}
```

也允许文章对象：

```json
{
  "articles": [
    {
      "article_title": "Battery failure analysis",
      "article_url": "https://example.com/articles/bms",
      "article": "Article text..."
    }
  ]
}
```

### 4.3 面向外部检索源开发者的接口规范

本节用于发给外部检索源开发者。开发者不需要理解 Onyx 内部的 `InferenceChunk`、RRF、persona 或 document set，只需要实现稳定的 HTTP 检索接口。

#### 4.3.1 基本要求

外部检索源必须提供一个可由 Onyx 后端访问的 HTTP endpoint：

```text
POST /search
Content-Type: application/json
Accept: application/json
```

必须满足：

1. 请求和响应均为 JSON。
2. 同一个请求在短时间内应尽量返回稳定结果。
3. 不相关时返回空结果数组，不要返回空 `content` 的结果。
4. 每条有效结果必须提供可用于回答的文本内容。
5. 单次请求应在配置的 timeout 内返回，MVP 建议 3 秒以内。
6. 不要在响应中返回敏感凭证、用户隐私数据或未授权数据。

#### 4.3.2 认证方式

MVP 支持以下认证方式之一：

```text
none
bearer token
api key header
basic auth
```

推荐使用 bearer token：

```http
Authorization: Bearer <token>
```

或 API key header：

```http
X-API-Key: <api-key>
```

外部服务不应要求浏览器 Cookie 认证，因为 Onyx 是后端服务到后端服务调用。

#### 4.3.3 请求格式

最小请求：

```json
{
  "query": "battery management failure causes",
  "limit": 10
}
```

推荐完整请求：

```json
{
  "schema_version": "1.0",
  "query": "battery management failure causes",
  "limit": 10,
  "filters": {
    "namespaces": ["engineering"],
    "entity_types": ["Component", "Issue"],
    "relation_types": ["caused_by", "depends_on"],
    "time_range": {
      "start": "2026-01-01T00:00:00Z",
      "end": null
    }
  },
  "options": {
    "max_hops": 2,
    "min_confidence": 0.65,
    "include_paths": true,
    "include_raw_graph": false
  },
  "context": {
    "request_id": "req-123",
    "tenant_id": "tenant-id",
    "user_id": "user-id"
  }
}
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---:|---|
| `query` | 是 | 用户问题或 Onyx 传入的主检索 query。 |
| `limit` | 否 | 希望返回的最大结果数。外部源可以返回更少结果。 |
| `schema_version` | 否 | 接口协议版本。建议返回中保持一致。 |
| `filters.namespaces` | 否 | 限制 ontology namespace 或业务域。 |
| `filters.entity_types` | 否 | 限制实体类型。 |
| `filters.relation_types` | 否 | 限制关系类型。 |
| `filters.time_range` | 否 | 限制时间范围。 |
| `options.max_hops` | 否 | 图谱路径最大跳数。非图谱源可忽略。 |
| `options.min_confidence` | 否 | Onyx 期望的最低置信度。外部源可用于提前过滤。 |
| `context.request_id` | 否 | 用于日志关联。建议原样写入服务日志。 |
| `context.tenant_id` | 否 | 多租户场景的租户标识。 |
| `context.user_id` | 否 | 调用用户标识。只应用于权限过滤和日志。 |

#### 4.3.4 响应格式

最小成功响应：

```json
{
  "results": [
    {
      "title": "Battery failure analysis",
      "content": "The battery management system failure is linked to ...",
      "url": "https://example.com/articles/battery-failure",
      "confidence": 0.82
    }
  ]
}
```

推荐完整响应：

```json
{
  "schema_version": "1.0",
  "request_id": "req-123",
  "results": [
    {
      "result_id": "result-001",
      "canonical_key": "component:battery_management_system",
      "fact_key": "component:battery_management_system|caused_by|issue:thermal_runaway",
      "title": "Battery Management System failure causes",
      "content": "The battery management system failure is linked to thermal runaway under ...",
      "url": "https://example.com/articles/bms-failure",
      "score": 0.86,
      "confidence": 0.82,
      "updated_at": "2026-05-20T10:00:00Z",
      "source": {
        "type": "ontology",
        "name": "Engineering Ontology",
        "source_id": "article-789"
      },
      "provenance": [
        {
          "source_id": "JIRA-123",
          "source_type": "jira",
          "title": "Battery failure analysis",
          "url": "https://jira.example.com/browse/JIRA-123",
          "updated_at": "2026-05-18T08:00:00Z"
        }
      ],
      "metadata": {
        "namespace": "engineering",
        "ontology_version": "v0.3.1"
      }
    }
  ],
  "warnings": [],
  "diagnostics": {
    "latency_ms": 120,
    "retrieval_mode": "hybrid_graph_article"
  }
}
```

响应字段说明：

| 字段 | 必填 | 说明 |
|---|---:|---|
| `results` | 是 | 结果数组。无匹配时返回空数组。 |
| `results[].content` | 是 | 每条有效结果的证据文本。不能为空。 |
| `results[].title` | 强烈建议 | 文章标题、实体标题或事实标题。Onyx 用于展示和引用。 |
| `results[].url` | 建议 | 可点击来源。没有 URL 时引用质量会降低。 |
| `results[].score` | 建议 | 检索相关性，建议 0 到 1。 |
| `results[].confidence` | 建议 | 事实可信度或外部源置信度，建议 0 到 1。 |
| `results[].result_id` | 建议 | 外部源内部结果 ID。可变也可以，但不应用作唯一去重依据。 |
| `results[].canonical_key` | 建议 | 实体级稳定业务 key。 |
| `results[].fact_key` | 建议 | 事实或关系级稳定业务 key。 |
| `results[].source.source_id` | 建议 | 原始文章、记录或节点的来源 ID。 |
| `results[].provenance` | 建议 | 事实来源证明。用于引用、排查和可信度判断。 |
| `results[].updated_at` | 建议 | 结果或来源最后更新时间，ISO 8601 格式。 |
| `warnings` | 否 | 非致命问题列表。 |
| `diagnostics` | 否 | 延迟、检索模式、版本等诊断信息。 |

#### 4.3.5 无匹配响应

当 query 与外部源数据不相关时，返回：

```json
{
  "results": [],
  "diagnostics": {
    "reason": "no_relevant_result"
  }
}
```

不要返回：

```json
{
  "results": [
    {
      "title": "No result",
      "content": "",
      "confidence": 0
    }
  ]
}
```

空 `content` 的 result 会被 Onyx 判定为 invalid。

#### 4.3.6 错误响应

外部服务应使用标准 HTTP 状态码：

| 状态码 | 场景 |
|---:|---|
| 200 | 请求成功。无结果也返回 200 + `results: []`。 |
| 400 | 请求格式错误，例如缺少 `query`。 |
| 401 | 认证缺失或无效。 |
| 403 | 已认证但无权限访问该数据范围。 |
| 408 | 外部服务自身请求超时。 |
| 429 | 限流。建议返回 `Retry-After` header。 |
| 500 | 服务内部错误。 |
| 503 | 服务暂不可用。 |

错误 body 建议：

```json
{
  "error": {
    "code": "invalid_query",
    "message": "query is required",
    "retryable": false
  }
}
```

运行时 Onyx 默认 fail-open：外部源报错不会阻断内部检索。

#### 4.3.7 性能要求

MVP 推荐：

```text
p50 latency <= 500ms
p95 latency <= 2500ms
timeout <= 3000ms
max results <= 10
content per result <= 6000 chars
response body <= 1MB
```

如果外部源需要复杂图谱查询，应先返回 top results，不要等待全量路径分析完成。长耗时诊断信息可以放入异步日志，不要阻塞检索响应。

#### 4.3.8 排序与置信度要求

`score` 和 `confidence` 建议分开：

```text
score: 这条结果和 query 的相关性。
confidence: 这条结果本身作为事实或证据的可信度。
```

如果只能提供一个数值：

```text
优先放在 confidence；
Onyx 可以降级把 confidence 当 score 使用。
```

数值范围建议统一为：

```text
0.0 <= value <= 1.0
```

#### 4.3.9 内容要求

`content` 应该是可直接放入 LLM 上下文的证据文本。建议：

1. 返回和 query 相关的段落或摘要，而不是整篇超长文章。
2. 不要只返回实体 ID、三元组 ID 或内部 JSON。
3. 不要返回 HTML 页面源码。
4. 如果必须返回结构化事实，也要同时提供自然语言 `content`。
5. 文本应保留必要上下文，例如主体、关系、结论和来源。

示例：

```json
{
  "title": "Battery Management System - thermal runaway",
  "content": "Battery Management System failures are associated with thermal runaway when temperature sensors report inconsistent values. This relation is supported by JIRA-123 and the 2026 failure analysis report.",
  "confidence": 0.82
}
```

#### 4.3.10 开发者自测清单

外部检索源交付前，应至少通过：

1. 正常 query 返回 1 到 10 条有效结果。
2. 无关 query 返回 `results: []`。
3. 每条有效结果都有非空 `content`。
4. title 为空时，确认 Onyx fallback 可以生成可读标题。
5. URL 为空时，确认这是可接受的引用降级。
6. score / confidence 在 0 到 1 范围内。
7. 认证失败返回 401。
8. 请求缺少 query 返回 400。
9. 服务超时不超过配置 timeout。
10. 同一 query 连续请求结果基本稳定。

curl 示例：

```bash
curl -X POST "https://ontology.example.com/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ONTOLOGY_TOKEN" \
  -d '{
    "query": "battery management failure causes",
    "limit": 5
  }'
```

## 5. 字段降级规则

统一 normalizer 负责把外部响应转成 `NormalizedExternalRetrievalResult`。规则必须集中在 `backend/onyx/external_retrieval/normalization.py`，不要散落在 adapter 里。

### 5.1 结果数组定位

结果路径优先级：

```text
configured result_path
  -> $.results
  -> $.data.results
  -> $.articles
  -> $.data.articles
  -> root array
```

如果找不到结果数组：

1. admin 测试接口返回 400，提示 `External response does not contain a result array`。
2. 运行时记录 warning，跳过该外部源，不阻断主检索。

### 5.2 content 字段

`content` 是每条可用检索结果的唯一硬性必要字段。外部源判断 query 与自身数据不相关时，应返回空结果集，而不是返回空 `content` 的结果。

推荐无匹配响应：

```json
{
  "results": [],
  "warnings": [],
  "diagnostics": {
    "reason": "no_relevant_result"
  }
}
```

每条非空结果必须能通过下列路径之一得到非空文本：

```text
configured content paths
  -> content
  -> evidence_text
  -> snippet
  -> text
  -> summary
  -> article
  -> article.content
  -> article.text
  -> article.body
  -> body
```

如果一条结果无法得到 content：

1. admin 测试中标记该条结果为 invalid。
2. 如果外部源返回了非空结果数组，但所有结果都 invalid，则测试接口返回 400。
3. 运行时丢弃 invalid 结果；如果全部丢弃，则外部源返回空结果。

如果外部源直接返回空结果数组，表示该 query 无匹配结果，不视为字段错误。

content 规范化：

1. strip 首尾空白。
2. 合并连续空白字符。
3. 去掉无法展示的控制字符。
4. 超过 `max_content_chars` 时截断，默认建议 6000 字符。
5. 保留原始 content hash 进入 metadata，便于排查。

### 5.3 title 字段

`title` 推荐提供，但不是硬性必要字段。降级优先级：

```text
configured title paths
  -> title
  -> article_title
  -> article.title
  -> entity.name
  -> source.title
  -> provenance[0].title
  -> url hostname/path
  -> content first line
  -> "External result <index>"
```

Onyx 映射时必须同时设置：

```text
InferenceChunk.title = normalized.title
InferenceChunk.semantic_identifier = normalized.title
```

原因：当前 Onyx downstream 更多使用 `semantic_identifier` 作为展示标题、引用标题和 LLM section title。

### 5.4 URL 与来源字段

URL 降级优先级：

```text
configured url paths
  -> url
  -> article_url
  -> link
  -> source.url
  -> provenance[0].url
```

如果没有 URL，不报错，但 citation 质量降低。admin 页面应显示 warning。

来源 ID 降级优先级：

```text
configured source_id paths
  -> source_id
  -> result_id
  -> id
  -> article_id
  -> source.source_id
  -> provenance[0].source_id
```

### 5.5 分数和置信度

字段语义：

```text
score: 检索相关性，主要用于排序。
confidence: 外部源对事实或文章可信度的判断。
```

降级规则：

```text
score
  -> configured score paths
  -> score
  -> relevance_score
  -> confidence
  -> rank-based score

confidence
  -> configured confidence paths
  -> confidence
  -> trust_score
  -> score
  -> null
```

score 应归一化到 0 到 1。如果外部源返回 0 到 100，可以通过 `score_scale = 100` 配置转换。

运行时排序建议：

```text
effective_score = normalized_score * source_weight
```

如果 `confidence` 低于配置的 `min_confidence`，默认丢弃该结果。没有 confidence 时不按 confidence 过滤，只记录 metadata。

### 5.6 稳定身份与去重 key

不要依赖外部源内部 ID。生成稳定身份时使用：

```text
dedupe_key =
  fact_key
  -> canonical_key + relation/path
  -> source_id
  -> url
  -> content_fingerprint
```

Onyx document id：

```text
document_id = "external_retrieval:" + source_id + ":" + sha256(dedupe_key)
chunk_id = result.chunk_index or 0
```

content fingerprint：

```text
content_fingerprint = sha256(normalized_content)
```

MVP 不做 embedding 去重。先做：

1. document_id + chunk_id 精确去重。
2. fact_key / canonical_key 去重。
3. url / source_id 去重。
4. normalized content hash 去重。
5. 可选 SimHash / MinHash 近似文本去重。

重复结果合并策略：

1. 保留 effective_score 更高的主结果。
2. 合并 provenance。
3. 合并 metadata 中不冲突字段。
4. 多来源支持同一事实时，可以提高 `metadata.provenance_count`，但不要直接修改 LLM 可见 content。

## 6. 适配器接口

### 6.1 Python Protocol

建议定义：

```python
from typing import Protocol

class ExternalRetrievalAdapter(Protocol):
    def validate_config(self, config: dict[str, object]) -> None:
        ...

    def search(
        self,
        request: ExternalRetrievalRequest,
        config: ExternalRetrievalSourceConfig,
    ) -> list[NormalizedExternalRetrievalResult]:
        ...

    def test(
        self,
        request: ExternalRetrievalTestRequest,
        config: ExternalRetrievalSourceConfig,
    ) -> ExternalRetrievalTestResult:
        ...
```

MVP adapter：

```text
http_json
```

后续 adapter：

```text
ontology
openapi
graphql
internal_service
```

### 6.2 HTTP JSON adapter 配置

```json
{
  "name": "Engineering Ontology",
  "adapter_type": "http_json",
  "enabled": true,
  "endpoint": "https://ontology.example.com/search",
  "method": "POST",
  "auth": {
    "type": "bearer",
    "token": "encrypted"
  },
  "headers": {
    "X-Client": "onyx"
  },
  "timeout_ms": 3000,
  "max_results": 10,
  "max_content_chars": 6000,
  "source_weight": 0.6,
  "min_confidence": 0.65,
  "request_mode": "standard",
  "call_strategy": "original_query_once",
  "result_path": "$.results",
  "field_mapping": {
    "title": ["$.title", "$.article_title", "$.article.title"],
    "content": ["$.content", "$.evidence_text", "$.article", "$.article.body"],
    "url": ["$.url", "$.article_url", "$.link"],
    "score": ["$.score", "$.relevance_score"],
    "confidence": ["$.confidence"],
    "source_id": ["$.source_id", "$.article_id", "$.id"],
    "updated_at": ["$.updated_at", "$.article_updated_at"]
  }
}
```

`call_strategy` 可选：

```text
original_query_once
  默认值。每次用户问题只调用一次外部源，避免 query expansion 放大外部源。

semantic_query_once
  使用 LLM rephrase 后的主语义 query 调一次。

per_expanded_query
  对每个扩展 query 调用。仅在外部源稳定、低成本、排序质量高时开启。
```

MVP 默认只实现 `original_query_once`。

## 7. 数据库设计

新增表建议：

```text
external_retrieval_source
  id
  name
  description
  adapter_type
  enabled
  credentials: encrypted json
  config: jsonb
  timeout_ms
  max_results
  source_weight
  min_confidence
  call_strategy
  created_by_user_id
  created_at
  updated_at

external_retrieval_source__document_set
  id
  external_retrieval_source_id
  document_set_id
  config: jsonb
```

`credentials` 中只存敏感内容，例如 token、api key、basic auth password。非敏感字段放 `config`。

DB 函数放在：

```text
backend/onyx/db/external_retrieval.py
```

核心函数：

```text
create_external_retrieval_source
update_external_retrieval_source
delete_external_retrieval_source
fetch_external_retrieval_source_by_id
fetch_all_external_retrieval_sources
fetch_enabled_external_retrieval_sources_for_document_sets
create_external_retrieval_source_document_set_mapping
delete_external_retrieval_source_document_set_mapping
```

## 8. 后端 API

新增 router：

```text
backend/onyx/server/external_retrieval/api.py
prefix = /external-retrieval
```

在 `backend/onyx/main.py` 注册 router。按照项目规则，新 FastAPI API 不使用 `response_model`，只给函数返回值类型。

Admin API：

```text
GET    /external-retrieval/sources
POST   /external-retrieval/sources
GET    /external-retrieval/sources/{id}
PATCH  /external-retrieval/sources/{id}
DELETE /external-retrieval/sources/{id}

POST   /external-retrieval/sources/{id}/validate
POST   /external-retrieval/sources/{id}/test
POST   /external-retrieval/sources/test-config

GET    /external-retrieval/adapter-schemas
GET    /external-retrieval/sources/{id}/status
```

请求从前端走：

```text
/api/external-retrieval/...
```

不要在前端直接调 `localhost:8080`。

### 8.1 测试接口

`POST /external-retrieval/sources/{id}/test`

请求：

```json
{
  "query": "battery management failure causes",
  "limit": 5,
  "include_raw_response": true
}
```

响应：

```json
{
  "success": true,
  "latency_ms": 142,
  "normalized_results": [
    {
      "document_id": "external_retrieval:12:abc",
      "title": "Battery failure analysis",
      "content_preview": "The battery management system...",
      "url": "https://example.com/articles/bms",
      "score": 0.82,
      "confidence": 0.74,
      "dedupe_key": "sha256:...",
      "warnings": []
    }
  ],
  "invalid_results": [],
  "warnings": [
    "Result 2 has no url; citation quality will be lower."
  ],
  "raw_response": {}
}
```

如果缺少必要字段：

```json
{
  "success": false,
  "error_code": "missing_required_content",
  "message": "All external results are missing content after fallback mapping.",
  "invalid_results": [
    {
      "index": 0,
      "reason": "No content candidate found.",
      "available_fields": ["title", "confidence"]
    }
  ]
}
```

## 9. Search pipeline 接入

### 9.1 推荐接入点

新增：

```text
backend/onyx/external_retrieval/retrieval.py
```

提供：

```python
def get_external_retrieval_functions(
    db_session: Session,
    user_id: UUID | None,
    source_types: list[DocumentSource] | None,
    document_set_names: list[str] | None,
) -> list[ExternalRetrievalInfo]:
    ...
```

`ExternalRetrievalInfo` 包含：

```text
source_id
source_name
retrieval_function
call_strategy
source_weight
```

在 `SearchTool` 中：

1. DB session 打开时预取 external source 配置。
2. 根据 persona document sets 过滤可用外部源。
3. 默认只对 `original_query` 调用一次外部源。
4. 与内部检索、Slack federated search 并行执行。
5. 参与 weighted RRF。

不要在 MVP 阶段把 external retrieval 直接塞进 `search_chunks` 的通用 federated retrieval 参数里，否则容易被 query expansion 调用多次。

### 9.2 source type

建议新增：

```text
DocumentSource.EXTERNAL_RETRIEVAL = "external_retrieval"
```

具体来源名称放入 metadata：

```text
metadata.external_source_id
metadata.external_source_name
metadata.external_adapter_type
```

后续如果 ontology 成为稳定一等来源，再考虑新增：

```text
DocumentSource.ONTOLOGY = "ontology"
```

MVP 不建议为每一个外部源动态扩展 `DocumentSource` enum。

### 9.3 InferenceChunk 映射

每个 normalized result 转成：

```text
document_id = generated stable document id
chunk_id = 0
blurb = first 512 chars of content
content = normalized content
source_links = {0: url} if url exists else null
image_file_id = null
section_continuation = false
source_type = DocumentSource.EXTERNAL_RETRIEVAL
semantic_identifier = normalized title
title = normalized title
boost = 0
score = effective_score
hidden = false
metadata = normalized metadata
match_highlights = []
doc_summary = ""
chunk_context = ""
updated_at = normalized updated_at
primary_owners = null
secondary_owners = null
is_federated = true
```

## 10. 错误和降级策略

### 10.1 Admin 测试阶段

严格模式：

1. endpoint 不可达，报错。
2. HTTP 非 2xx，报错。
3. JSON 解析失败，报错。
4. 找不到结果数组，报错。
5. 所有结果缺少 content，报错。
6. 部分结果缺少 content，展示 invalid result，但允许保存配置，除非管理员开启 `strict_result_validation`。

### 10.2 运行时检索阶段

默认 fail-open：

1. 外部源超时，跳过该源。
2. 外部源返回异常，跳过该源。
3. normalized 后无有效结果，返回空。
4. 主检索和 LLM 回答继续执行。

需要记录：

```text
source_id
source_name
tenant_id
query request_id
latency_ms
result_count
invalid_result_count
error_code
warning
```

可选配置：

```text
fail_closed = false
```

MVP 不建议允许管理员开启 fail-closed。

## 11. 前端设计

### 11.1 菜单结构

新增 admin 一级菜单：

```text
External Retrieval
```

页面：

```text
/admin/external-retrieval
  外部检索源列表

/admin/external-retrieval/new
  新建外部检索源

/admin/external-retrieval/[id]
  编辑配置

/admin/external-retrieval/[id]/test
  独立测试和结果预览
```

### 11.2 列表页

桌面布局：

```text
Header: External Retrieval Sources + New Source button

Toolbar:
  search input
  enabled filter
  adapter type filter

Table:
  Name
  Adapter
  Endpoint hostname
  Enabled
  Bound document sets
  Last test status
  Timeout
  Max results
  Actions
```

列表页重点不是营销式卡片，而是可扫描、可运维。适合表格或 dense list。

### 11.3 新建/编辑页

建议分为 4 个区域：

```text
Basic
  name
  description
  enabled
  adapter_type

Connection
  endpoint
  method
  auth type
  token / api key
  headers
  timeout

Result Mapping
  result_path
  title paths
  content paths
  url paths
  score paths
  confidence paths
  source_id paths

Retrieval Behavior
  max_results
  source_weight
  min_confidence
  max_content_chars
  call_strategy
  document sets
```

交互要求：

1. `Test Connection` 只验证 endpoint、auth、HTTP 状态。
2. `Run Test Query` 调用完整检索和 normalizer。
3. 保存前如果没有通过字段测试，展示 warning，但可允许保存 disabled 状态。
4. 已启用状态下保存配置，必须至少通过一次 `Run Test Query` 或由管理员显式确认。

### 11.4 测试页

测试页需要让接入简单、可解释：

```text
Left panel:
  query input
  limit
  include raw response toggle
  run button

Right panel:
  status summary
  latency
  valid result count
  invalid result count
  normalized result preview
  warnings
  raw response viewer
```

Normalized result preview 展示：

```text
title
content preview
url
score
confidence
dedupe_key
metadata badges
warnings
```

不要只显示 raw JSON；raw JSON 只能作为调试折叠区。

### 11.5 Chat Thinking 区检索过程展示改造

外部检索源接入后，Chat 消息中的 thinking 区不能只显示笼统的 `Thinking...` 或 `Searching internal documents`。需要把它改造成可观测的 retrieval timeline，展示系统正在查询哪些数据源、各数据源状态、返回结果和最终读取的证据。

注意：这里展示的是检索过程，不是 LLM 私有推理链。不要把外部源过程塞进 `ReasoningDelta`。应扩展 search tool 的 streaming packet，让 thinking 区显示可验证的检索行为。

当前前端搜索过程主要由以下 packet 驱动：

```text
SearchToolStart
SearchToolQueriesDelta
SearchToolDocumentsDelta
SectionEnd
```

对应渲染路径：

```text
web/src/app/app/message/messageComponents/timeline/renderers/search/InternalSearchToolRenderer.tsx
web/src/app/app/message/messageComponents/timeline/renderers/search/searchStateUtils.ts
web/src/app/app/message/messageComponents/timeline/hooks/useTimelineHeader.ts
```

这些 packet 只能表达“正在搜索内部文档 / 正在阅读”，无法表达外部数据源的过程。建议新增 search source progress packet。

#### 11.5.1 新增 Search Source Progress Packet

后端新增 packet：

```python
class SearchToolSourceProgressDelta(BaseObj):
    type: Literal["search_tool_source_progress_delta"] = (
        StreamingType.SEARCH_TOOL_SOURCE_PROGRESS_DELTA.value
    )

    sources: list[SearchSourceProgress]
```

建议模型：

```python
class SearchSourceProgress(BaseModel):
    source_id: str
    source_name: str
    source_kind: Literal[
        "internal",
        "external",
        "federated",
        "web",
    ]
    status: Literal[
        "pending",
        "searching",
        "normalizing",
        "completed",
        "empty",
        "skipped",
        "timeout",
        "error",
    ]
    result_count: int | None = None
    accepted_count: int | None = None
    invalid_count: int | None = None
    latency_ms: int | None = None
    warning: str | None = None
```

示例 packet：

```json
{
  "type": "search_tool_source_progress_delta",
  "sources": [
    {
      "source_id": "internal",
      "source_name": "Internal documents",
      "source_kind": "internal",
      "status": "searching",
      "result_count": 0,
      "accepted_count": 0,
      "latency_ms": null,
      "warning": null
    },
    {
      "source_id": "external-retrieval-1",
      "source_name": "Engineering Ontology",
      "source_kind": "external",
      "status": "completed",
      "result_count": 8,
      "accepted_count": 3,
      "invalid_count": 2,
      "latency_ms": 420,
      "warning": "2 results dropped because content was missing"
    }
  ]
}
```

#### 11.5.2 SearchToolStart 带 source plan

`SearchToolStart` 建议扩展可选字段：

```python
class SearchToolStart(BaseObj):
    type: Literal["search_tool_start"] = StreamingType.SEARCH_TOOL_START.value
    is_internet_search: bool = False
    planned_sources: list[SearchPlannedSource] = Field(default_factory=list)
```

```python
class SearchPlannedSource(BaseModel):
    source_id: str
    source_name: str
    source_kind: Literal["internal", "external", "federated", "web"]
```

这样搜索一开始前端就能展示：

```text
Searching knowledge sources

Internal documents       Pending
Engineering Ontology     Pending
Slack                    Pending
```

对于 `call_strategy = original_query_once` 的外部检索源，后端应在拿到 original query 和 external source 配置后立即启动外部检索，不等待 query expansion。UI 上也应尽早显示外部源为 `searching`。

#### 11.5.3 Thinking 区文案调整

当前 timeline header 的兜底文案是 `Thinking...`。接入外部检索源后，搜索阶段建议改为：

```text
Searching knowledge sources
Reading retrieved evidence
```

规则：

1. 只要当前 step 是 search tool，header 不再显示 `Thinking...`。
2. source progress 中存在 `searching` / `normalizing` 状态时，显示 `Searching knowledge sources`。
3. 已有 accepted documents 且检索未完成时，显示 `Reading retrieved evidence`。
4. search tool 完成后，折叠状态可显示 `Read N sources` 或 `Read N documents`。

`web/src/app/app/message/messageComponents/timeline/hooks/useTimelineHeader.ts` 需要基于扩展后的 search state 计算 header。

#### 11.5.4 Expanded Retrieval Timeline 布局

搜索 step 展开后建议显示三段：

```text
Search terms
  [battery failure] [BMS thermal issue]

Sources
  Internal documents       Searching...
  Engineering Ontology     3 accepted / 8 returned · 420ms
  Slack                    No relevant results

Reading
  [Battery failure analysis]
  [BMS thermal runaway]
  [JIRA-123]
```

设计要求：

1. 使用现有 timeline renderer 架构，不新增独立聊天消息块。
2. `Search terms` 继续使用现有 `SearchChipList`。
3. `Sources` 新增轻量 source status list，使用稳定行高，避免 streaming 时布局跳动。
4. `Reading` 继续使用结果 chip，但结果 chip 需要显示来源 badge。
5. 外部源状态行使用 muted warning 表达非致命异常，不使用整体错误样式。

#### 11.5.5 外部源失败展示

外部源运行时默认 fail-open。UI 不应把外部源失败展示成整个回答失败。

建议文案：

```text
Engineering Ontology timed out. Continuing with internal documents.
```

```text
Engineering Ontology returned no relevant results.
```

```text
Engineering Ontology skipped 2 results with missing content.
```

视觉规则：

1. `timeout` / `error` 使用 muted warning。
2. `empty` 使用普通 muted text。
3. `completed` 使用正常状态。
4. 不在最终答案区强插错误提示；只在 thinking / retrieval timeline 中展示。

#### 11.5.6 结果按来源展示

外部源接入后，结果不能只混在一个列表里。Expanded 状态下建议支持来源维度展示：

```text
All
Internal
External
Web
```

MVP 可以先不做 tab，只在结果 chip / details card 上显示来源 badge：

```text
Engineering Ontology
Internal documents
Slack
```

来源信息从 `SearchDoc.source_type` 和 `metadata.external_source_name` 读取。

推荐结果详情字段：

```text
title
source badge
content preview / blurb
url
updated_at
score
metadata tags
```

#### 11.5.7 后端触发时机与 UI 事件顺序

为了减少延迟，外部源检索应与内部检索并行，且 `original_query_once` 策略不等待 query expansion。

推荐事件顺序：

```text
1. SearchToolStart(planned_sources)
2. SearchToolSourceProgressDelta(all sources pending)
3. Start external retrieval with original_query
4. Start query expansion
5. SearchToolSourceProgressDelta(external sources searching)
6. Query expansion completes
7. SearchToolQueriesDelta(expanded queries)
8. Start internal retrieval with expanded queries
9. SearchToolSourceProgressDelta(internal searching)
10. External / internal results return independently
11. SearchToolSourceProgressDelta(source completed / empty / timeout / error)
12. SearchToolDocumentsDelta(final fused documents)
13. SectionEnd
```

前端不能假设 `SearchToolQueriesDelta` 一定早于 source progress。source progress 可能先出现。

#### 11.5.8 历史消息回放

当前 `backend/onyx/server/query_and_chat/session_loading.py` 会根据已保存 tool calls 重建 search packets。新增 source progress 后，需要考虑历史回放：

1. MVP 可以不持久化每个 source 的中间状态。
2. 历史消息至少应能从 saved search docs 推断结果来源，重建一个 completed source summary。
3. 如果 tool_call 中保存了 external retrieval diagnostics，则优先用 diagnostics 重建完整 source progress。
4. 没有 diagnostics 时，不展示 source progress timeline，只展示现有 queries 和 documents。

#### 11.5.9 前端实现点

需要更新：

```text
web/src/app/app/services/streamingModels.ts
  新增 PacketType.SEARCH_TOOL_SOURCE_PROGRESS_DELTA
  新增 SearchToolSourceProgressDelta / SearchSourceProgress 类型
  扩展 SearchToolStart.planned_sources

web/src/app/app/message/messageComponents/timeline/renderers/search/searchStateUtils.ts
  从 packets 中聚合 source progress
  输出 sources、active source count、accepted count、hasExternalSources

web/src/app/app/message/messageComponents/timeline/renderers/search/InternalSearchToolRenderer.tsx
  增加 Sources 区块
  Reading 结果 chip 增加来源 badge

web/src/app/app/message/messageComponents/timeline/hooks/useTimelineHeader.ts
  基于 search source progress 更新 header 文案
```

后端需要更新：

```text
backend/onyx/server/query_and_chat/streaming_models.py
  新增 StreamingType
  新增 pydantic models

backend/onyx/tools/tool_implementations/search/search_tool.py
  emit planned sources
  emit source progress
  external retrieval 和 internal retrieval 状态更新

backend/onyx/server/query_and_chat/session_loading.py
  历史消息可选重建 source summary
```

## 12. 权限与安全

1. Admin 创建、编辑、删除外部检索源需要 curator 或 admin 权限。
2. 普通用户不能看到外部源凭证。
3. 凭证字段使用 encrypted json / encrypted string。
4. 测试接口不得把 secret 回传给前端。
5. 外部 endpoint 需要 SSRF 防护：
   - 默认禁止访问 localhost、metadata IP、私网地址，除非显式开启 internal service allowlist。
   - 允许配置 host allowlist。
6. header 中禁止覆盖敏感内部 header，例如 tenant、cookie、authorization，除非字段来自 encrypted credentials。
7. 记录 raw response 时默认只在 admin test 返回，不进入普通日志。

## 13. 可观测性

MVP 日志即可，后续可加 metrics。

日志字段：

```text
external_retrieval.source_id
external_retrieval.source_name
external_retrieval.adapter_type
external_retrieval.call_strategy
external_retrieval.latency_ms
external_retrieval.result_count
external_retrieval.valid_result_count
external_retrieval.invalid_result_count
external_retrieval.timeout
external_retrieval.error_code
```

Search UI / Chat debug 可选展示：

```text
External source used: Engineering Ontology
External results accepted: 3 / 5
External latency: 142ms
```

## 14. 测试计划

### 14.1 后端单元测试

覆盖：

1. 标准完整响应 normalizer。
2. 文章简化响应 normalizer。
3. result path 降级。
4. content 字段降级。
5. title 字段降级。
6. score / confidence 归一化。
7. 缺少 content 的 invalid result。
8. 全部缺少 content 时抛出配置测试错误。
9. document_id / dedupe_key 生成稳定。
10. 重复结果合并。

建议路径：

```text
backend/tests/unit/external_retrieval/test_normalization.py
backend/tests/unit/external_retrieval/test_dedupe.py
```

### 14.2 后端集成测试

覆盖：

1. mock HTTP endpoint 成功返回。
2. mock HTTP endpoint 超时。
3. mock HTTP endpoint 非 2xx。
4. test API 返回 normalized preview。
5. runtime search fail-open。
6. disabled source 不参与检索。
7. document set 未绑定时不参与 persona 检索。

### 14.3 前端测试

覆盖：

1. 列表页加载、空状态、错误状态。
2. 新建页字段校验。
3. 测试查询成功展示 normalized preview。
4. 测试查询失败展示 missing content 错误。
5. 保存 disabled source 不要求测试成功。
6. 保存 enabled source 需要测试通过或显式确认。

前端如果新增 E2E，按项目 Playwright 规范落到现有 E2E 体系。

## 15. 分阶段交付

### Phase 0: 设计与约束确认

交付：

1. 本文档。
2. 外部响应字段契约确认。
3. MVP 只支持 `http_json` adapter。
4. MVP 只支持 `original_query_once`。

### Phase 1: 后端 MVP

交付：

1. DB 表和 alembic migration。
2. `ExternalRetrievalSource` DB CRUD。
3. `http_json` adapter。
4. normalizer 和 fallback。
5. test API。
6. source disabled / enabled 生效。
7. runtime fail-open。

不交付：

1. embedding 去重。
2. 多 adapter。
3. 外部源结果质量 dashboard。

### Phase 2: Search 接入

交付：

1. `SearchTool` 中调用 enabled external sources。
2. 默认原始 query 只调用一次。
3. external results 转为 `InferenceChunk`。
4. 参与 weighted RRF。
5. document set / persona 绑定生效。
6. source_weight / min_confidence 生效。

验收：

1. 外部源关闭时，检索结果完全不变。
2. 外部源超时时，主检索仍可返回。
3. 外部源返回不合法数据时，主检索仍可返回。
4. 外部源开启时，引用中能看到外部证据标题。

### Phase 3: Admin UI

交付：

1. 独立菜单 `/admin/external-retrieval`。
2. 列表、新建、编辑、测试页面。
3. Result mapping 可配置。
4. 测试结果 normalized preview。
5. document set 绑定配置。

验收：

1. 管理员不看后端日志也能判断字段映射是否成功。
2. 管理员可以禁用外部源。
3. 管理员可以用测试 query 看到有效结果、无效结果和 warning。

### Phase 4: 质量增强

交付：

1. SimHash / MinHash 近似去重。
2. 最近测试状态持久化。
3. latency / success rate 指标。
4. 多 external source 并发和限流。
5. `semantic_query_once` 和 `per_expanded_query`。

### Phase 5: Ontology 专用增强

交付：

1. `ontology` adapter preset。
2. entity / relation / path 字段专用预览。
3. ontology namespace、entity type、relation type 管理。
4. ontology 结果与普通文章结果的 provenance 合并。
5. 稳定后可选建设 indexed connector，把稳定文章同步入 Vespa。

## 16. 验收标准

MVP 完成标准：

1. 管理员可以在独立菜单创建 HTTP JSON 外部检索源。
2. 管理员可以配置 endpoint、auth、字段映射、timeout、max results、source weight。
3. 管理员可以运行测试 query，并看到 normalized results。
4. 外部响应只有文章和置信度时，可以通过 fallback 正常接入。
5. 外部响应缺少所有 content 候选字段时，测试接口明确报错。
6. 外部源启用后，指定 document set / persona 的检索可以使用外部结果。
7. 外部源关闭后，不影响原有检索。
8. 外部源超时、异常、返回坏数据时，主检索不失败。
9. 外部结果在最终引用中有可读 title。
10. 不使用 embedding 作为实时去重主路径。

## 17. 关键设计决策

1. 外部源是独立 admin 能力，不继续混在普通 connector 列表里。
2. MVP 使用 HTTP JSON adapter，而不是 ontology 专用 adapter。
3. 运行时默认 fail-open，避免外部源破坏主检索。
4. `content` 是唯一硬性必要字段；title、url、score、confidence 都有 fallback。
5. Onyx 自己生成稳定 `document_id`，不依赖外部源内部 ID。
6. 默认只对 original query 调用一次外部源，避免 query expansion 放大。
7. 前端测试页必须展示 normalized preview，而不只是 raw JSON。
8. 如果后续 ontology 稳定，再考虑 indexed connector 或 ontology 专用 adapter。
