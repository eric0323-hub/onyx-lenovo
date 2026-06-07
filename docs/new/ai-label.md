# AI 标签与 Taxonomy 标签治理已落地功能梳理

## 1. 文档定位

本文档以当前仓库已经落地的实现为准，梳理“标签治理 / Taxonomy”模块已经具备的功能、关键逻辑、实现细节和当前边界。

本文档不是未来需求文档。原文档中已经描述但代码中尚未落地的能力，已在本文档中移除或降级为“当前未实现”。后续产品、测试和开发对齐时，应以本文档中的“已落地能力”和“当前未实现能力”为准。

主要代码入口：

| 类型 | 位置 |
| --- | --- |
| 管理端页面 | `web/src/refresh-pages/admin/TaxonomyPage/` |
| 管理端路由 | `web/src/app/admin/taxonomy/*` |
| 后端 API | `backend/onyx/server/taxonomy/api.py` |
| 数据库读写 | `backend/onyx/db/taxonomy.py` |
| LLM 生成、摘要、打标、自检 | `backend/onyx/taxonomy/llm_service.py` |
| 批量文章导入 | `backend/onyx/taxonomy/article_import.py` |
| 导入后台任务 | `backend/onyx/background/celery/tasks/taxonomy/tasks.py` |
| Query 到 Taxonomy 匹配 | `backend/onyx/taxonomy/search_matcher.py` |
| 检索接入 | `backend/onyx/context/search/pipeline.py`、`backend/onyx/server/query_and_chat/query_backend.py` |
| Taxonomy 元数据常量 | `backend/onyx/taxonomy/constants.py` |

---

## 2. 当前已落地功能总览

当前模块已经落地以下能力：

1. 管理员创建、编辑、保存、激活三级 Taxonomy 草稿。
2. 基于管理员提示词流式生成三级标签体系。
3. 可配置 Taxonomy 生成参数和两段生成 Prompt 模板。
4. 保存 Taxonomy 版本，并将一个版本设为当前生效版本。
5. 查看当前生效版本、版本历史、节点数量和基础健康摘要。
6. 管理端批量导入 Markdown / PDF 文章。
7. 文章导入后进入专用 Celery 队列，完成文档入库、Summary 生成和自动打标尝试。
8. 为文档生成可编辑 Summary。
9. Summary 人工修改后，将既有有效标签标记为需重新打标，并尝试自动重新打标。
10. 基于当前生效 Taxonomy 执行批量 AI 打标。
11. 支持基于 Summary 或原文内容打标。
12. 支持一篇文档命中多个三级 leaf 标签。
13. 支持低置信度标签进入 `needs_review` 状态。
14. 支持打标失败或未匹配时写入失败标记。
15. 支持可选 Taxonomy Optimization：候选新增 leaf 标签、健康自检、复用已有标签或生成新版本。
16. 将有效 Taxonomy 标签投影为普通文档 metadata tag，供检索过滤消费。
17. 支持手动 Taxonomy 节点过滤转换为 leaf 标签过滤。
18. 支持 query 到 Taxonomy leaf 的 embedding 匹配和 Query Match 管理测试页。
19. 支持在配置开启且模式允许时，为检索追加 Taxonomy leaf 过滤分支并合并结果。
20. 所有 Taxonomy 相关 LLM 调用已使用专门的 `LLMFlow` tracing 标记。

---

## 3. 管理端页面与入口

### 3.1 管理侧边栏入口

管理端侧边栏有“标签治理”分组，当前直接展示：

1. `标签体系`：`/admin/taxonomy/template-draft`
2. `文章管理`：`/admin/taxonomy/imports`

`/admin/taxonomy` 会重定向到 `/admin/taxonomy/template-draft`。

### 3.2 已实现的 Taxonomy 子页面

| 页面 | 路由 | 已落地能力 |
| --- | --- | --- |
| 标签体系 | `/admin/taxonomy/template-draft` | 输入提示词生成三级 Taxonomy、树视图编辑、JSON 编辑、保存草稿、激活版本 |
| 文章管理 | `/admin/taxonomy/imports` | 导入 Markdown/PDF、查看文章 Summary、标签、覆盖率、处理状态、删除导入文章 |
| 生成参数 | `/admin/taxonomy/generation-config` | 配置 X/Y/M/N/P 数量参数和两段 Prompt 模板 |
| 版本历史 | `/admin/taxonomy/history` | 查看当前生效版本、版本列表、基础健康摘要 |
| Summaries | `/admin/taxonomy/summaries` | 手动生成 Summary、编辑 Summary |
| Batch Tagging | `/admin/taxonomy/batch-tagging` | 按文档 ID 或最近文档批量打标，选择 Summary/原文和优化开关 |
| Query Match | `/admin/taxonomy/query-match` | 测试 query 到 Taxonomy leaf 的匹配结果 |

注意：部分子页面没有直接出现在左侧一级导航中，但已由路由和页面组件实现。

---

## 4. Taxonomy 数据模型与状态

### 4.1 Taxonomy

当前只支持企业级 Taxonomy：`TaxonomyScope.ENTERPRISE`。

后端 `get_or_create_taxonomy` 当前取数据库中第一条 Taxonomy 记录作为当前企业标签体系；创建时默认名称为 `Enterprise Knowledge Taxonomy`，前端保存草稿时使用 `企业知识库标签体系`。

主要字段：

1. `id`
2. `name`
3. `scope`
4. `active_version_id`
5. `default_language`
6. `industry_context`
7. `company_description`
8. `owner_user_id`
9. `created_at`
10. `updated_at`

### 4.2 Taxonomy Version

每次保存草稿都会创建一个新的 `taxonomy_version`。

已实现状态：

1. `draft`
2. `active`
3. `superseded`
4. `deprecated`

已实现来源：

1. `default_template`
2. `ai_generated`
3. `manual`
4. `tagging_optimization`

当前前端保存草稿时，版本来源写入为 `manual`；节点本身仍可保留 `ai_generated` 来源。

激活版本时：

1. 当前版本状态变为 `active`。
2. 同一 Taxonomy 下旧的 active 版本变为 `superseded`。
3. Taxonomy 的 `active_version_id` 指向该版本。
4. 草稿节点状态会从 `draft` 改为 `active`。
5. 写入一条 `ACTIVATE_VERSION` 变更记录。

### 4.3 Taxonomy Node

当前固定三级：

1. `l1`
2. `l2`
3. `leaf`

文档最终只绑定 `leaf` 节点。

节点已落地字段：

1. 稳定 ID：`id`
2. 版本 ID：`version_id`
3. 父节点：`parent_id`
4. 层级：`level`
5. 稳定编码：`code`
6. 名称：`name`
7. 展示名称：`display_name`
8. 完整路径：`full_path`
9. 路径节点 ID 列表：`path_node_ids`
10. 排序：`sort_order`
11. 定义：`definition`
12. 适用范围：`applicability`
13. 不适用范围：`exclusion`
14. 正例：`positive_examples`
15. 反例：`negative_examples`
16. 关键词：`keywords`
17. 同义词：`synonyms`
18. 打标指导：`tagging_guidance`
19. 冲突规则：`conflict_rules`
20. 来源：`source`
21. 来源详情：`source_detail`
22. 状态：`status`
23. 替代节点：`replacement_node_id`
24. 停用原因：`disabled_reason`
25. 创建/更新人和时间

节点来源 enum 已包含：

1. `system_default`
2. `industry_template`
3. `ai_generated`
4. `manual`
5. `task_generated`

节点状态 enum 已包含：

1. `draft`
2. `active`
3. `modified`
4. `disabled`
5. `deleted`

当前 UI 中的新增、修改、删除节点发生在草稿树上，本质是编辑一棵待保存的新版本树；尚未实现对生效版本的单节点更新、停用、删除 API。

### 4.4 基础健康摘要

创建版本时会生成 `health_summary`，当前包含：

1. `l1_count`
2. `l2_count`
3. `leaf_count`
4. `duplicate_names`
5. `leaf_nodes_missing_examples`

版本历史页会展示重复名称和 leaf 缺少示例等基础问题。

当前没有对整棵 Taxonomy 做完整 LLM 健康自检报告，也没有人工维护时的影响分析报告。

---

## 5. 默认模板能力

### 5.1 后端已实现

后端已实现默认模板 API：

`GET /admin/taxonomy/default-template`

默认模板位于 `backend/onyx/taxonomy/default_template.py`，当前包含 6 个一级分类：

1. 公司治理与合规
2. 人力资源文档
3. 财务、法务与合同
4. 技术与研发
5. 运营与客户
6. IT、质量与安全

后端创建草稿接口也支持传入 `selected_default_leaf_ids`，会把被选中的默认 leaf 及其祖先节点合并进草稿树。

### 5.2 前端当前未接入

当前前端标签体系页面没有展示默认模板选择树，也没有管理员按 leaf 多选启用默认模板的交互。

前端保存草稿时固定传：

```ts
selected_default_leaf_ids: []
```

因此，当前不能把“管理员可以在 UI 中按三级 leaf 多选默认模板”作为已落地功能或验收项。

---

## 6. Taxonomy 生成与草稿编辑

### 6.1 生成方式

当前生成入口在 `/admin/taxonomy/template-draft`。

管理员输入一段业务背景提示词后，前端调用：

`POST /admin/taxonomy/generate-draft/stream`

后端以 SSE 流式返回阶段进度和部分节点，前端实时填充树视图和 JSON 编辑区。

非流式接口也存在：

`POST /admin/taxonomy/generate-draft`

当前前端主流程使用流式接口。

### 6.2 分层生成逻辑

LLM 生成分为三步：

1. 生成一级/二级标签。
2. 为每个二级标签并行生成三级 leaf。
3. 对完整三级树做最终优化。

细节逻辑：

1. 一级/二级生成使用 `LLMFlow.TAXONOMY_LAYERED_DRAFT_GENERATION`。
2. 三级 leaf 生成也使用 `LLMFlow.TAXONOMY_LAYERED_DRAFT_GENERATION`。
3. 最终优化使用 `LLMFlow.TAXONOMY_DRAFT_OPTIMIZATION`。
4. LLM 需要输出 JSON 对象。
5. 对 OpenAI/Azure provider 会请求 JSON object response format。
6. 如果 JSON 解析失败，会调用 JSON repair 流程：`LLMFlow.TAXONOMY_JSON_REPAIR`。
7. 最终树必须通过 `validate_taxonomy_tree` 校验。
8. 如果最终优化失败，会保留优化前生成树。

### 6.3 生成参数

生成参数在 `/admin/taxonomy/generation-config` 管理，并存储在 KV 配置中。

默认参数：

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| X | 4 | 一级/二级初始候选数量倍数 |
| Y | 20 | 一级 + 二级最终数量上限 |
| M | 4 | 每个二级下三级候选数量倍数 |
| N | 6 | 每个二级下 leaf 最终数量上限 |
| P | 10 | leaf 并行生成并发数 |

前端支持编辑：

1. `l1_l2_prompt_template`
2. `leaf_prompt_template`
3. X/Y/M/N/P 数量参数

模板中的变量会在前端渲染为实际参数，再传给后端 runtime config。

### 6.4 草稿编辑

生成后，管理员可以：

1. 在树视图中新增一级节点。
2. 给一级节点新增二级节点。
3. 给二级节点新增 leaf 节点。
4. 编辑节点字段。
5. 删除草稿树中的节点。
6. 切换 JSON 视图直接编辑完整树。
7. 填写本次修改说明。
8. 保存为草稿版本。
9. 将草稿设为生效版本。

前端会做结构和字段校验。后端保存和激活时还会再次校验：

1. 根节点必须为 `l1`。
2. `l1` 下必须是 `l2`。
3. `l2` 下必须是 `leaf`。
4. 非 leaf 节点必须有 children。
5. leaf 节点不能有 children。
6. 所有节点必须有 `definition`。
7. 所有节点必须有 `applicability`。
8. 所有节点必须至少有一个 keyword。
9. leaf 必须至少有一个正例和一个反例。

### 6.5 生成恢复

前端会把正在生成的 Taxonomy 临时写入 `localStorage`，刷新页面后可恢复生成状态并继续执行。

---

## 7. 文章导入与 Summary

### 7.1 文章导入入口

文章导入在 `/admin/taxonomy/imports`。

当前导入前要求已有生效 Taxonomy。若没有生效版本，前端会阻止导入并提示先启用标签体系。

支持文件类型：

1. Markdown：`.md`
2. Markdown：`.markdown`
3. PDF：`.pdf`

### 7.2 导入处理链路

前端调用：

`POST /admin/taxonomy/articles/import`

后端处理：

1. 校验文件名和扩展名。
2. 将文件保存到 FileStore。
3. 发送 Celery 任务 `PROCESS_TAXONOMY_ARTICLE_IMPORT`。
4. 队列为 `taxonomy_processing`。
5. 优先级为 high。
6. 任务带 `expires=CELERY_TAXONOMY_ARTICLE_IMPORT_TASK_EXPIRES`，当前为 15 分钟。
7. 任务参数包含 `tenant_id`。

Celery 任务中：

1. 用 `LocalFileConnector` 解析文件。
2. 生成导入文档 ID：`taxonomy_article__<file_id>`，多文档时追加 `__<index>`。
3. 设置 source 为 `FILE`。
4. 设置 `from_ingestion_api=True`。
5. 写入 metadata：
   - `taxonomy_article_import`
   - `taxonomy_article_file_id`
   - `taxonomy_article_file_name`
   - `taxonomy_article_imported_by`
6. 调用 `index_ingestion_documents` 入库和索引。
7. 对缺少 complete Summary 的文档写入 pending Summary。
8. 调用 Summary 生成。

### 7.3 Summary 生成

Summary 生成逻辑位于 `generate_summaries_for_documents`。

输入来源：

1. 若传入 document IDs，则处理指定文档。
2. 否则按 `Document.last_modified desc` 取最近文档，受 `limit` 限制。

生成逻辑：

1. 使用默认 LLM，temperature 为 0。
2. 从当前文档索引中按 document ID 拉取 chunks。
3. 拼接内容，最多取 12000 字符。
4. 调用 `LLMFlow.TAXONOMY_SUMMARY`。
5. 要求 LLM 输出 JSON：`{"summary": "..."}`。
6. Prompt 要求中文 Summary 控制在 120-220 个中文字符。
7. 成功写入 `DocumentTaxonomySummary`，状态为 `complete`。
8. 失败写入状态 `failed` 和 failure reason。

Summary 状态：

1. `pending`
2. `complete`
3. `failed`

### 7.4 Summary 人工编辑

管理员可以在文章管理页或 Summaries 页编辑 Summary。

保存后：

1. Summary 标记为 `is_manual=True`。
2. Summary 状态为 `complete`。
3. 该文档当前 `active` 或 `tagging_failed` 的 Taxonomy 标签会被标记为 `needs_retag`。
4. invalidation reason 为 `Summary was manually edited`。
5. 系统随后尝试基于当前 Summary 自动重新打标。
6. 若没有生效 Taxonomy 或自动打标失败，会记录日志并跳过，不阻塞 Summary 保存。

如果批量生成 Summary 时 `overwrite_manual=False`，已有人工 Summary 不会被覆盖。

### 7.5 覆盖率统计

Dashboard 当前返回：

1. `total_documents`
2. `labeled_documents`
3. `coverage_percent`

实现细节：当前 `total_documents` 统计的是 `document` 表总数，`labeled_documents` 统计有 active Taxonomy 标签的去重文档数，并不限定只统计 taxonomy article import 文档。

---

## 8. 批量 AI 打标

### 8.1 入口与执行方式

批量打标页面为 `/admin/taxonomy/batch-tagging`。

后端接口：

`POST /admin/taxonomy/tagging/run`

当前批量打标在 API 请求中同步执行，执行完后返回任务结果；不是 Celery 后台任务。

前端可配置：

1. 文档 ID 列表，可为空。
2. 打标来源：`summary` 或 `original`。
3. limit，默认 50。
4. 是否开启 Taxonomy Optimization。
5. Optimization Strength 文本。

若没有生效 Taxonomy，接口会报错。

### 8.2 文档选择

后端选择文档规则：

1. 传入 `document_ids` 时，打标指定文档。
2. 未传入时，按 `Document.last_modified desc` 取最近文档。
3. 数量受 `limit` 限制，接口上限 500。

### 8.3 打标输入内容

若 source 为 `summary`：

1. 文档存在 complete Summary 且有 summary 文本时，使用 Summary。
2. 否则回退到原文索引内容。

若 source 为 `original`：

1. 从文档索引按 document ID 拉取 chunks。
2. 拼接后最多取 12000 字符。

### 8.4 AI 推荐 leaf 标签

每个文档调用 `recommend_taxonomy_tags`。

输入：

1. 文档标题。
2. 打标输入内容。
3. 当前生效版本下 active leaf 节点列表。
4. 是否开启 optimization。

Prompt 约束：

1. 只能从候选 leaf ID 中选择标签。
2. 可多标签，通常 1-3 个。
3. confidence 为 0 到 1。
4. 无法覆盖时写 `unmatched_reason`。
5. 只有 `enable_optimization=true` 时才允许输出 candidates。
6. candidates 必须是完整三级路径，`path` 长度为 3。

结果写入 `document_taxonomy_tag`。

### 8.5 标签状态与置信度

当前自动推荐标签按环境变量阈值决定状态：

`TAXONOMY_TAG_CONFIDENCE_ACTIVE_THRESHOLD`

默认值为 `0.7`。

规则：

1. confidence 大于等于阈值：`active`
2. confidence 小于阈值：`needs_review`

第一条推荐标签会标记为 `is_primary=True`。

标签结果记录：

1. document ID
2. leaf node ID
3. version ID
4. task ID
5. full path snapshot
6. confidence
7. source
8. primary / sort order
9. evidence
10. unmatched reason
11. tagging source content
12. prompt version：`taxonomy_mvp_v1`
13. model info
14. review status
15. assignment status

当前没有管理端人工确认、驳回、修改单条标签的 UI 或 API；`review_status` enum 已存在，但工作流未落地。

### 8.6 重新打标与失效

每次对文档执行打标前，会将该文档已有 `active` 或 `tagging_failed` 标签标记为：

`needs_retag`

原因类似：

`Retagged by taxonomy task <task_id>`

随后写入本次新标签结果。

### 8.7 未匹配和失败标记

如果文档处理异常，或候选处理后仍没有任何 `active` / `needs_review` 标签，系统会写入一条失败 marker：

1. `leaf_node_id = null`
2. `full_path_snapshot = "打标签失败"`
3. `confidence = 0`
4. `status = tagging_failed`
5. `unmatched_reason` 存失败原因

任务最终状态：

1. 无失败文档：`complete`
2. 有失败文档：`completed_with_errors`

`failed` 和 `pending` enum 已存在，但当前同步执行主流程一般返回 `complete` 或 `completed_with_errors`。

---

## 9. Taxonomy Optimization 与候选新增标签

### 9.1 开启方式

批量打标页面支持开关：

`Taxonomy Optimization`

后端请求字段：

1. `enable_optimization`
2. `optimization_strength`

文章导入后自动打标也会尝试启用 optimization，取决于环境变量：

`TAXONOMY_AUTO_TAGGING_ENABLE_OPTIMIZATION`

当前默认值为 `true`。

### 9.2 候选标签产生

只有开启 optimization 时，打标 LLM 才会解析 `candidates`。

候选标签字段：

1. 完整三级 path
2. definition
3. evidence
4. confidence
5. redundancy result
6. suggested reuse node ID

候选标签写入 `taxonomy_candidate_label`，初始状态为：

`pending_review`

### 9.3 健康自检 Agent

批量打标结束后，会统一调用 `review_taxonomy_candidate_labels`。

使用 `LLMFlow.TAXONOMY_HEALTH_CHECK`。

输入：

1. 本批次候选新增标签。
2. 当前基础版本 active leaf 节点。
3. 当前基础版本 active l2 节点。
4. optimization strength。

Agent 输出 action：

1. `reuse_existing`
2. `add_leaf`
3. `reject`
4. `needs_handling`

关键约束：

1. 新增标签是例外，不是默认行为。
2. 优先复用已有 leaf。
3. `add_leaf` 只能挂到已有二级节点下。
4. 不允许新增一级或二级主干。
5. 如果候选需要新增一级或二级，输出 `needs_handling`。
6. 批量内候选之间也要去重。

### 9.4 复用已有标签

若 action 为 `reuse_existing`：

1. candidate 状态变为 `reused_existing`。
2. 写入 `suggested_reuse_node_id`。
3. 给触发文档新增一条 `task_generated` 来源的 active 标签。
4. 如果本批次同时生成了新版本，会把复用标签 remap 到新版本对应 leaf。

### 9.5 新增 leaf 并生成新版本

若存在 `add_leaf` 决策：

1. 后端以当前 active 版本为基础复制一棵新树。
2. 只在已有 L2 下追加新 leaf。
3. 新 leaf code 形如：`task_<task_id>_<candidate_id>_<slug>`。
4. 同一批次按 `(parent_l2_node_id, leaf_name_slug)` 去重。
5. 创建并立即激活一个新版本。
6. 新版本来源为 `tagging_optimization`。
7. 旧 active 版本变为 `superseded`。
8. 当前任务已有标签会按 node code remap 到新版本。
9. candidate 状态变为 `task_added`。
10. 给触发文档新增一条 `task_generated` 来源的 active 标签。

该逻辑已经处理“任务运行期间 active version 可能变化”的情况：候选处理时会优先取当前最新 active version 作为 base version，并按稳定 code remap 任务标签。

### 9.6 当前未实现的优化交互

当前没有候选标签人工审核页面。

候选标签的健康自检、复用、拒绝、需处理、新增版本逻辑在后端自动执行；管理员不能在 UI 中逐条确认候选标签。

当前也没有开启 optimization 前的强二次确认弹窗，只有一条提示卡说明可能创建候选 leaf 标签。

---

## 10. 标签投影与检索消费

### 10.1 投影到文档 metadata tag

打标完成后，会调用 `project_taxonomy_tags_to_document_metadata`。

该函数会先删除文档旧的 Taxonomy 投影 tag，再把当前 active version 下的 active Taxonomy 标签投影为普通 metadata tag。

投影 key：

1. `taxonomy_version`
2. `taxonomy_l1_id`
3. `taxonomy_l2_id`
4. `taxonomy_leaf_id`
5. `taxonomy_path`

投影只包含 `active` 标签，不包含 `needs_review`、`needs_retag` 或失败 marker。

### 10.2 手动 Taxonomy 节点过滤

搜索过滤模型已经包含：

1. `taxonomy_node_ids`
2. `taxonomy_leaf_ids`

当用户或调用方传入 `taxonomy_node_ids` 时，后端会将 L1/L2/leaf 节点展开为当前 active version 下的 active leaf IDs，然后放入 `taxonomy_leaf_ids`。

OpenSearch 和 Vespa 都已支持 `taxonomy_leaf_ids` 过滤。

实现细节：

1. Taxonomy leaf 过滤使用 metadata list。
2. 过滤条件 key 为 `taxonomy_leaf_id::<leaf_id>`。
3. Taxonomy leaf filter 是独立 filter clause，不会和普通 metadata tags 混在同一个 OR 组里。
4. ACL、tenant、document set、source、time 等原有过滤仍然共同生效。

### 10.3 Query 自动匹配 Taxonomy

`match_taxonomy_query` 已实现 query 到 active leaf 的 embedding 匹配。

匹配逻辑：

1. 读取当前 settings 转成 `TaxonomySearchConfig`。
2. 若 Taxonomy Search disabled 且没有 manual node IDs，直接返回 disabled。
3. 校验 `apply_to` 是否匹配 settings。
4. 读取当前 active Taxonomy nodes。
5. 自动匹配只处理 leaf 节点。
6. 使用当前 search settings 对应 embedding model。
7. 对 leaf 的完整路径和 definition 分别做 embedding。
8. Query embedding 与两类 leaf embedding 算 cosine similarity。
9. 置信度计算：`max(name_score, 0.4 * name_score + 0.6 * definition_score)`。
10. 返回 top 10 candidates。
11. 使用 leaf threshold 或 default threshold，默认 0.8。
12. 支持 timeout 检查，默认 100ms。
13. leaf embedding 有进程内 cache，cache key 包含版本、节点指纹和 embedding model 指纹。

若传入 manual node IDs，则不走自动 embedding 匹配，直接展开 leaf，并返回 `hard_filter` decision。

### 10.4 检索主链路接入

在普通 search pipeline 中：

1. 先构造普通 filters。
2. 如果用户已经手动选择 Taxonomy filter，不再做自动匹配。
3. 如果配置允许自动 Taxonomy Search，则先计算 query embedding 并调用 `match_taxonomy_query`。
4. 先执行普通检索。
5. 若 decision 为 `augment_search` 且有 expanded leaf IDs，再执行一次带 taxonomy leaf filter 的检索分支。
6. 两路结果用 `combine_retrieval_results` 合并。
7. Taxonomy 匹配失败会记录日志并继续普通检索。

Admin Search 中也有类似的 Taxonomy augment 分支。

### 10.5 当前配置与 UI 边界

Settings model 中已包含较多 Taxonomy Search 配置字段，例如 mode、apply_to、各层级阈值、timeout、max leaf expansion、coverage requirement 等。

但当前 Chat Preferences UI 只暴露：

1. Taxonomy Search 开关。
2. Default Confidence。

并且 UI 保存开关时会带默认配置，其中 `taxonomy_search_mode` 默认为 `suggest_only`。

因此：

1. Query Match 页面可用于测试建议匹配。
2. 手动 Taxonomy filter 已可作为严格过滤使用。
3. 自动检索增强的后端逻辑已实现。
4. 仅通过当前 UI 打开 Taxonomy Search 时，默认是 `suggest_only`，不会触发主检索链路中的自动 augment 分支。
5. `soft_filter_with_fallback`、`hard_filter`、L1/L2 阈值、coverage requirement、min results fallback 等配置字段已存在，但当前主流程没有完整实现这些高级策略。

---

## 11. API 能力清单

当前已实现的主要管理 API：

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/admin/taxonomy/dashboard` | 当前 Taxonomy、覆盖率、最近 Summary、最近任务 |
| GET | `/admin/taxonomy/default-template` | 默认模板树 |
| GET | `/admin/taxonomy/generation-config` | 获取生成配置 |
| PUT | `/admin/taxonomy/generation-config` | 更新生成配置 |
| POST | `/admin/taxonomy/generate-draft` | 非流式生成 Taxonomy 草稿 |
| POST | `/admin/taxonomy/generate-draft/stream` | 流式生成 Taxonomy 草稿 |
| POST | `/admin/taxonomy/draft` | 保存草稿版本 |
| POST | `/admin/taxonomy/version/{version_id}/activate` | 激活版本 |
| GET | `/admin/taxonomy/versions` | 版本列表 |
| POST | `/admin/taxonomy/summaries/generate` | 批量生成 Summary |
| PUT | `/admin/taxonomy/summaries/{document_id}` | 人工更新 Summary |
| POST | `/admin/taxonomy/articles/import` | 导入 Markdown/PDF 文章 |
| DELETE | `/admin/taxonomy/articles/{document_id}` | 删除导入文章 |
| POST | `/admin/taxonomy/tagging/run` | 执行批量打标 |
| GET | `/admin/taxonomy/documents/{document_id}/tags` | 查看文档 Taxonomy 标签 |
| POST | `/admin/taxonomy/match-query` | 测试 query 到 Taxonomy 匹配 |

注意：当前没有单独的节点 update / move / disable / delete API；前端是在草稿树中编辑完整 Taxonomy，然后保存成新版本。

---

## 12. LLM Tracing

当前 Taxonomy 模块的 LLM 调用已使用专门 flow：

1. `LLMFlow.TAXONOMY_SUMMARY`
2. `LLMFlow.TAXONOMY_LAYERED_DRAFT_GENERATION`
3. `LLMFlow.TAXONOMY_DRAFT_OPTIMIZATION`
4. `LLMFlow.TAXONOMY_JSON_REPAIR`
5. `LLMFlow.TAXONOMY_TAGGING`
6. `LLMFlow.TAXONOMY_HEALTH_CHECK`

这符合项目要求：LLM 调用必须使用 `LLMFlow` enum，不直接传字符串。

---

## 13. 当前未实现或不能按原文档验收的能力

以下能力在原规划文档中出现过，但当前代码未完整落地，不能作为已开发功能验收。

### 13.1 默认模板 UI 选择

后端有默认模板 API 和 `selected_default_leaf_ids` 合并逻辑，但前端没有默认模板选择界面，保存草稿时始终传空数组。

### 13.2 基于知识库内容自动生成 Taxonomy

当前 Taxonomy 生成主要基于管理员输入的提示词和生成配置。接口字段包含 `organization_context`、`knowledge_scope`、`classification_preferences`，但当前前端主入口只把提示词作为 `company_description` 传入，没有自动抽取知识库文档标题、目录、Summary 或内容样本参与生成。

### 13.3 生效版本的单节点维护

当前 UI 支持编辑草稿树并保存新版本，但没有对当前生效版本单独执行：

1. 单节点修改 API
2. 单节点移动 API
3. 单节点停用 API
4. 单节点删除 API
5. 节点替代关系维护 API

### 13.4 节点变更影响分析

数据库有 `taxonomy_change_record` 表，并且创建和激活版本会写变更记录。

但当前没有实现删除/停用/移动节点前的影响分析，也没有展示受影响文档数量和代表性文档的完整流程。

### 13.5 未打标签池 / 待重新打标池

当前有标签状态：

1. `needs_review`
2. `needs_retag`
3. `depends_on_disabled_label`
4. `tagging_failed`

但没有独立的“未打标签池”或“待重新打标池”页面，也没有基于这些池子的批量入队工作流。

管理员当前可以通过文档 ID 和 limit 手动触发批量打标。

### 13.6 人工确认标签结果

`review_status` enum 已存在：

1. `unconfirmed`
2. `confirmed`
3. `rejected`
4. `modified`

但当前没有 UI/API 支持管理员逐条确认、驳回或修改文档标签。

### 13.7 候选新增标签人工审核

候选标签表和后端自动健康自检已实现。

当前没有候选标签列表页，也没有管理员逐条接受、拒绝、修改后接受、复用已有标签的 UI。

### 13.8 完整软过滤、硬过滤和回退策略

后端 enum 和配置字段已包含 `soft_filter_with_fallback`、`hard_filter` 等模式，但当前自动 Taxonomy 检索主流程实际行为是：

1. 先普通检索。
2. 再追加 Taxonomy leaf 分支。
3. 合并结果。

当前没有实现：

1. Taxonomy 自动硬过滤作为唯一结果范围。
2. taxonomy filtered result 不足时按 `min_results` 自动回退的完整策略。
3. L1/L2 自动命中和层级 fallback。
4. coverage requirement gating。

### 13.9 高频标签使用分析

当前没有 Taxonomy query 命中日志、标签使用热度、搜索效果评估或高频分类统计页面。

### 13.10 自动标签合并

当前没有自动合并已有标签能力。

健康自检 Agent 只会对候选新增标签建议复用、追加 leaf、拒绝或需处理，不会合并已有节点。

---

## 14. 当前可验收口径

按当前已落地功能，验收应围绕以下结果：

1. 管理员能输入提示词，流式生成三级 Taxonomy。
2. 管理员能在树视图或 JSON 视图编辑草稿。
3. 草稿保存时会做三级结构和必填字段校验。
4. 草稿能保存为版本，并能设为生效版本。
5. 激活新版本后，旧 active 版本变为 superseded。
6. 版本历史页能展示当前生效树、版本列表、节点数量和基础健康摘要。
7. 生成参数页能调整 X/Y/M/N/P 和 Prompt 模板。
8. 有生效 Taxonomy 后，管理员能导入 Markdown/PDF 文章。
9. 导入文章会进入 `taxonomy_processing` Celery 队列。
10. 导入完成后会生成 Summary。
11. Summary 可查看和编辑。
12. Summary 编辑后，既有 active / tagging_failed 标签会变为 `needs_retag`，并尝试自动重新打标。
13. 管理员能手动生成 Summary。
14. 管理员能发起批量打标，选择 Summary 或原文。
15. 打标结果可包含多个 leaf 标签。
16. 标签置信度低于阈值时进入 `needs_review`。
17. 未匹配或失败时写入 `tagging_failed` marker。
18. 开启 optimization 后，候选新增标签会进入健康自检。
19. 健康自检可复用已有 leaf、拒绝、标记需处理，或在已有 L2 下新增 leaf。
20. 新增 leaf 会创建并激活新的 `tagging_optimization` 版本。
21. 有效 active 标签会投影为 `taxonomy_leaf_id` 等 metadata tag。
22. 手动 Taxonomy node filter 能展开到 active leaf IDs 并参与检索过滤。
23. Query Match 能返回 leaf 匹配、候选、置信度、reason 和 expanded leaves。
24. 在后端配置允许非 `suggest_only` 模式时，检索主链路能追加 Taxonomy leaf 过滤分支并合并结果。
25. Taxonomy 相关 LLM 调用都能在 tracing 中看到对应 `LLMFlow`。

---

## 15. 推荐后续补齐项

以下不是当前已开发功能，只是基于现状的后续补齐建议：

1. 接入默认模板选择 UI，让 `selected_default_leaf_ids` 真正可用。
2. 将知识库样本、已生成 Summary 或导入文章内容接入 Taxonomy 生成上下文。
3. 增加候选新增标签审核页。
4. 增加文档标签人工确认、驳回和修改工作流。
5. 增加 `needs_review`、`needs_retag`、`tagging_failed` 的治理列表和批量重新打标入口。
6. 增加对生效 Taxonomy 的单节点维护 API，并配套影响分析。
7. 完整实现 Taxonomy Search 的 soft filter、hard filter、coverage gating 和 min result fallback。
8. 在 Chat Preferences 中暴露 mode、apply_to、timeout、max leaf expansion 等关键配置。
9. 增加 query 命中日志、标签使用率、覆盖率按导入文章/全库拆分统计。
