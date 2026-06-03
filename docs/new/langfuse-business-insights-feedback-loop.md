# 基于 Langfuse 的 LLM 应用业务洞察与 Feedback 闭环提升模块新增需求

## 1. 文档目的

本文档用于明确当前项目在已初步集成 Langfuse 的基础上，如何进一步建设面向业务、产品、运营和管理人员可使用的 LLM 应用业务洞察与反馈闭环能力。

本文档描述的是现有 Onyx 项目内的一个增强模块，不是独立产品。该模块依赖当前项目已有的聊天、检索、用户反馈、管理后台、Query History、Usage Report、tracing、Langfuse 接入和权限体系。

本文档重点说明“需要实现什么”“业务人员如何使用”“闭环如何形成”“分阶段如何落地”。本文档不展开具体数据库表结构、接口字段、Prompt 细节、前端组件设计或调度实现。

---

## 2. 模块定位与适用范围

本模块的目标不是简单把 Langfuse 控制台链接放进 Onyx，而是将 LLM trace、成本、延迟、反馈、评分、Prompt 版本和业务上下文转化为业务人员能够理解并行动的洞察。

本模块聚焦以下 6 个核心能力：

1. 建立统一的业务观测数据规范，让每条关键 LLM trace 都带可分析的业务上下文。
2. 将 Onyx 现有用户反馈与 Langfuse trace 建立稳定关联。
3. 提供面向业务人员的质量、成本、延迟、使用量和反馈看板。
4. 对负反馈、质量下降、成本异常、延迟异常和版本发布影响进行自动发现与提醒。
5. 定期生成 LLM 观测报告，降低人工 review 成本。
6. 支持从问题发现到 Prompt、RAG、Eval、模型配置优化，再到效果验证的闭环流程。

本模块的使用对象包括：

1. 业务运营人员：关注用户是否解决问题、常见失败模式、负反馈和业务趋势。
2. 产品经理：关注功能模块表现、版本改动影响、用户群体差异和改进优先级。
3. 客户成功或交付团队：关注重点客户、部门、用户群体的使用质量与风险。
4. 管理员和工程团队：关注追踪覆盖率、成本、延迟、错误、Prompt 版本和数据治理。

---

## 3. 当前项目基础

当前项目已经具备以下基础能力，可作为本模块的落地起点：

1. Langfuse tracing processor 已通过 `backend/onyx/tracing/setup.py` 接入，配置 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY` 后可启用。
2. Onyx 已有 `LLMFlow` 注册表，所有 LLM、embedding、rerank、image、voice、intent-classification 调用都应带明确 flow。
3. Admin 后台已有 `/admin/performance/observability` 入口，可查看 Langfuse 配置状态并发送 sample traces。
4. 当前 Langfuse processor 会把 trace metadata 中的 `chat_session_id` 提升为 Langfuse `session_id`，把 `user_id` 提升为 Langfuse `user_id`。
5. Chat message feedback 已存在，支持点赞、点踩、反馈文本和 predefined feedback。
6. Document retrieval feedback 已存在，可记录检索结果点击和 endorse/reject/hide 等反馈。
7. EE 已有 Query History 和 Usage Report，可作为 Onyx 内部业务分析数据源。
8. 项目已有 Prometheus metrics 和管理后台使用量页面，可与 Langfuse 数据互补。

当前需要补齐的关键缺口：

1. 业务 metadata 还没有统一规范，trace 在业务维度上不可稳定聚合。
2. Chat feedback 与 Langfuse trace 没有形成一等关联，业务人员很难从负反馈直接跳到对应 trace。
3. Langfuse 数据尚未转化为 Onyx 内部可消费的业务洞察和报告。
4. 当前 Observability 页面偏工程配置验证，不足以支撑运营复盘。
5. Prompt 版本、RAG 配置、模型配置与质量变化之间尚未形成可追溯的 before/after 验证流程。

---

## 4. 核心原则

### 4.1 业务维度先行

所有关键 trace 必须携带稳定的业务上下文。没有业务 metadata 的 trace 只能用于工程排障，不能用于运营分析、质量归因或版本复盘。

### 4.2 先用 Langfuse，再做 Onyx 聚合

Langfuse 已提供 tracing、scores、feedback、custom dashboards、prompt management、datasets 和 experiments 等能力。Onyx 不应重造 Langfuse 控制台，而应负责：

1. 补齐 Onyx 特有业务上下文。
2. 将反馈和业务对象关联到 Langfuse trace。
3. 生成 Onyx 内部可读的聚合洞察、提醒和报告。
4. 提供深链回 Langfuse trace、dashboard、dataset 和 experiment 的入口。

### 4.3 闭环必须可衡量

每一次优化都必须能回答：

1. 改动前的问题是什么。
2. 影响了哪些功能、用户群体、Prompt 版本或模型配置。
3. 改动后质量、反馈、成本、延迟是否改善。
4. 是否产生新的副作用。

### 4.4 数据安全优先

Langfuse 中可能保存 prompt、回答、检索上下文、工具输出、用户标识、metadata 和 token/cost 数据。生产启用本模块前必须明确脱敏、保留周期、访问权限和审计要求。

---

## 5. 统一观测数据规范

### 5.1 Trace 必带业务字段

关键聊天、检索、Agent、RAG、工具调用、Prompt 生成、rerank、embedding 和评估 trace 应尽量携带以下 metadata：

| 字段 | 含义 | 要求 |
| --- | --- | --- |
| `tenant_id` | 租户或企业 ID | 多租户场景必填 |
| `user_id` | Onyx 用户 ID | 已登录用户必填 |
| `chat_session_id` | 会话 ID | 聊天场景必填，需映射到 Langfuse session |
| `user_message_id` | 用户消息 ID | 聊天生成场景建议必填 |
| `assistant_message_id` | 助手消息 ID | 聊天生成场景建议必填 |
| `feature` | 功能入口 | 必填，例如 chat、search、nrf、slack_bot、user_file、taxonomy |
| `module` | 子模块 | 建议填写，例如 retrieval、rerank、generation、tool_call、memory、citation |
| `assistant_id` | Assistant/persona ID | 使用 persona 时必填 |
| `assistant_name` | Assistant/persona 名称 | 建议填写，便于业务人员识别 |
| `llm_flow` | `LLMFlow` 值 | LLM 相关调用必填 |
| `prompt_name` | Prompt 名称 | 使用可版本化 Prompt 时必填 |
| `prompt_version` | Prompt 版本 | 使用可版本化 Prompt 时必填 |
| `model_provider` | 模型提供商 | LLM 调用必填 |
| `model_name` | 模型名称 | LLM 调用必填 |
| `retrieval_profile` | 检索配置或索引策略 | RAG 场景建议填写 |
| `query_category` | 查询类别 | 可由规则、人工或 LLM 分类生成 |
| `user_segment` | 用户分群 | 可选，例如 admin、end_user、department、paid_tier |
| `release_version` | Onyx 发布版本或实验版本 | 生产发布、A/B 测试时必填 |
| `experiment_id` | 实验 ID | A/B 或灰度实验时必填 |

### 5.2 业务字段命名约束

1. 字段名必须稳定，不得在不同调用点混用同义字段。
2. 枚举值应使用小写 snake_case，便于 Langfuse、BI 和 SQL 聚合。
3. PII 或敏感业务字段不得直接进入 metadata，必须使用内部 ID、分群或脱敏值。
4. 新增 metadata 字段前应确认是否能被业务人员理解和使用。
5. 对于无法稳定识别的业务字段，可以先为空，不应填入猜测值。

### 5.3 Trace 覆盖率要求

本模块上线前，应建立 trace 覆盖率检查：

1. Langfuse dashboard 中不得长期出现大量 `untagged_invoke` 或 `untagged_stream`。
2. 核心聊天回答必须能按 `chat_session_id`、`user_id`、`assistant_id`、`feature`、`llm_flow` 查询。
3. 负反馈样本必须能回溯到原始 assistant message 和 Langfuse trace。
4. RAG 场景必须能区分 retrieval、rerank、context assembly 和 generation 的表现。

---

## 6. Feedback 采集与 trace 关联

### 6.1 显式反馈

现有点赞、点踩和反馈文本应保留，并增强为业务可分析反馈：

1. 点赞和点踩必须关联到 `chat_message_id`。
2. 点赞和点踩应能进一步关联到对应 Langfuse trace。
3. 点踩时应支持选择标准化原因，例如：
   - `incorrect_answer`：答案错误。
   - `missing_context`：缺少上下文。
   - `irrelevant_sources`：引用资料不相关。
   - `too_slow`：响应过慢。
   - `too_verbose`：过于冗长。
   - `unsafe_or_sensitive`：存在安全或敏感内容风险。
   - `bad_format`：格式不符合预期。
   - `tool_failure`：工具调用失败。
4. 反馈文本保留自由输入，用于后续聚类和报告生成。

### 6.2 隐式反馈

MVP 阶段建议先采集少量高价值隐式反馈，不追求复杂行为分析：

1. 是否重新生成回答。
2. 是否复制回答。
3. 是否点击引用来源。
4. 是否继续追问。
5. 是否在很短时间内关闭或放弃会话。

隐式反馈只作为趋势信号，不应直接等同于质量分数。

### 6.3 检索反馈

RAG 质量分析需要同时使用 document retrieval feedback：

1. 记录用户点击了哪些引用或检索结果。
2. 记录检索结果的 endorse/reject/hide 行为。
3. 将检索反馈与 `chat_message_id`、`document_id`、`document_rank` 和 trace metadata 关联。
4. 在报告中区分“检索失败”和“生成失败”，避免所有负反馈都归因到模型。

### 6.4 Langfuse feedback 与 Onyx feedback 同步

推荐把 Onyx 作为反馈采集入口，Langfuse 作为观测和分析入口：

1. 用户在 Onyx 前端提交反馈。
2. Onyx 写入自身 feedback 表。
3. 后端异步或同步将标准化 score/feedback 写入 Langfuse。
4. Langfuse score/comment 中应包含 Onyx `chat_message_id` 和必要深链。
5. 写入 Langfuse 失败不应阻断用户反馈提交，但必须记录可重试状态或错误日志。

---

## 7. 业务 Scores 体系

### 7.1 Score 类型

本模块应支持三类 score：

1. 用户反馈 score：来自点赞、点踩、原因选择、反馈文本。
2. 系统规则 score：来自延迟、成本、引用数量、检索结果点击、错误状态等确定性规则。
3. LLM-as-Judge score：由评估模型对回答质量、检索相关性、任务完成度等进行自动评分。

### 7.2 MVP 推荐 Scores

MVP 阶段建议优先建设以下 score：

| Score | 来源 | 用途 |
| --- | --- | --- |
| `user_satisfaction` | 点赞/点踩 | 衡量用户主观满意度 |
| `task_completion` | LLM-as-Judge + 抽检 | 判断问题是否被解决 |
| `retrieval_relevance` | LLM-as-Judge + 检索反馈 | 判断引用和检索上下文是否相关 |
| `answer_groundedness` | LLM-as-Judge | 判断回答是否基于检索内容 |
| `answer_clarity` | LLM-as-Judge | 判断回答是否清晰可执行 |
| `safety_risk` | 规则 + LLM-as-Judge | 识别敏感、违规或不安全回答 |
| `cost_efficiency` | 系统规则 | 衡量质量和成本的平衡 |

### 7.3 Score 约束

1. Score 名称必须稳定，避免同一含义多种命名。
2. 每个 score 必须有定义、取值范围、来源和解释口径。
3. LLM-as-Judge score 必须记录 judge prompt 版本、judge 模型和评估时间。
4. Score 不能替代人工判断，低置信度或高风险样本必须进入人工 review。
5. Score 结果应回写 Langfuse，便于在 Langfuse 中按 trace、session、user、prompt version 和 feature 分析。

---

## 8. 业务看板需求

### 8.1 Langfuse 内置看板

应优先在 Langfuse 内建立以下看板：

1. 工程健康看板：
   - trace count。
   - p50/p95/p99 latency。
   - error rate。
   - token usage。
   - cost trend。
   - provider/model 分布。
2. 质量看板：
   - 各 score 均值和分布。
   - 点赞、点踩、反馈原因趋势。
   - 负反馈 trace 列表。
   - `untagged_*` trace 占比。
3. RAG 看板：
   - retrieval relevance。
   - rerank latency。
   - source click-through rate。
   - 引用缺失或引用低相关样本。
   - 按 connector、document set、retrieval profile 聚合的失败样本。
4. 版本看板：
   - prompt version 对比。
   - model version 对比。
   - release version 前后对比。
   - experiment variant 对比。

### 8.2 Onyx 内部业务洞察页

Langfuse 控制台适合工程和分析人员，但业务人员需要更收敛的视图。Onyx 管理后台应新增“LLM 业务洞察”页面，建议放在 Performance/Observability 相关区域。

该页面 MVP 至少展示：

1. 当前健康度总览：
   - 最近 24 小时 / 7 天 trace 数。
   - 点赞率和点踩率。
   - 平均质量 score。
   - p95 latency。
   - 估算成本。
   - 负反馈数量。
2. Top 风险列表：
   - 负反馈最多的 assistant。
   - 质量下降最明显的 feature。
   - 成本增长最快的 model/provider。
   - 延迟异常的 flow。
   - RAG 相关性最低的 connector 或 document set。
3. 可操作样本列表：
   - 负反馈 trace。
   - 低 score trace。
   - 高成本低质量 trace。
   - 错误 trace。
   - 每条样本都需要支持跳转到 Onyx chat session 和 Langfuse trace。
4. 时间和维度过滤：
   - 时间范围。
   - feature。
   - assistant。
   - user segment。
   - prompt version。
   - model provider/model。
   - feedback type。

### 8.3 外部 BI 扩展

如果需要给运营、财务或管理层做更复杂的统计，可在第二阶段接入外部 BI：

1. Langfuse Cloud 可优先使用 Metrics API v2。
2. 自托管 Langfuse v3 当前不应默认依赖 Metrics API v2，应保留 Metrics API v1、ClickHouse 只读视图或后续 SDK/API 升级方案。
3. 可选 BI 工具包括 Superset、Grafana、Power BI、Tableau 或 Retool。
4. 外部 BI 只读取聚合数据，不应默认暴露原始 prompt、回答或检索上下文。

---

## 9. 异常检测与趋势预警

### 9.1 异常类型

本模块应识别以下异常：

1. 质量异常：
   - 点踩率突增。
   - `task_completion` 或 `answer_groundedness` 均值下降。
   - 特定 assistant、feature 或 prompt version 质量低于基线。
2. 成本异常：
   - 单次请求成本异常。
   - 某模型或功能成本持续增长。
   - token 使用量与 trace count 不成比例增长。
3. 延迟异常:
   - p95/p99 latency 超阈值。
   - retrieval、rerank、tool call 或 generation 某一阶段异常变慢。
4. 错误异常：
   - provider error 增长。
   - tool call failure 增长。
   - indexing 或 user file 相关 LLM flow 失败增长。
5. 数据质量异常：
   - `untagged_*` 占比升高。
   - 缺少 `chat_session_id`、`feature`、`llm_flow` 等核心 metadata。
   - feedback 无法关联 trace。

### 9.2 检测方式

MVP 阶段建议使用简单、可解释的检测方式：

1. 固定阈值：例如 p95 latency 超过阈值。
2. 环比变化：例如 7 天点踩率相比前 7 天上升超过阈值。
3. 低样本保护：样本数不足时不触发强告警，只展示观察状态。
4. 维度拆解：整体异常必须能下钻到 feature、assistant、prompt version、model 和 user segment。

后续可扩展：

1. z-score。
2. IQR。
3. 季节性趋势模型。
4. Isolation Forest 等轻量异常检测。

### 9.3 告警与通知

告警应进入业务可消费通道：

1. Onyx 管理后台提醒。
2. Slack、企业微信或 Email。
3. 每条告警必须包含：
   - 异常类型。
   - 影响范围。
   - 指标变化。
   - Top 样本。
   - Langfuse dashboard 链接。
   - Langfuse trace 链接。
   - 建议处理人或处理团队。

---

## 10. LLM 观测报告

### 10.1 报告定位

LLM 观测报告用于把指标、异常、负反馈和样本 trace 转化为业务人员能阅读的结构化洞察。报告不是替代人工 review，而是帮助团队更快找到值得 review 的问题。

### 10.2 报告周期

MVP 支持每周报告，后续支持每日简报和重大异常即时报告。

### 10.3 报告输入

报告生成应使用以下输入：

1. Langfuse 聚合指标。
2. Onyx feedback 数据。
3. Query History 和 Usage Report 聚合结果。
4. 低 score 和负反馈 trace 样本。
5. 异常检测结果。
6. Prompt version、model version、release version 对比。
7. 业务目标配置，例如重点 assistant、重点客户、重点 feature。

### 10.4 报告结构

报告必须结构化，至少包含：

1. 执行摘要：
   - 健康度评分。
   - Top 3 发现。
   - 本周优先处理事项。
2. 指标趋势：
   - 使用量。
   - 点赞率 / 点踩率。
   - 质量 score。
   - 成本。
   - 延迟。
3. 异常与风险：
   - 异常说明。
   - 影响范围。
   - 样本链接。
   - 根因假设。
4. 用户反馈洞察：
   - 高频反馈原因。
   - 代表性反馈文本摘要。
   - 常见失败模式。
5. RAG 质量洞察：
   - 检索相关性。
   - 引用问题。
   - 需要优化的 connector、document set 或检索配置。
6. 成本优化机会：
   - 高成本低质量 flow。
   - 可降级模型或优化 prompt 的场景。
7. 行动建议：
   - Prompt 调整。
   - Eval 数据集补充。
   - RAG 优化。
   - 模型配置调整。
   - 产品交互优化。
8. 上次行动项复盘：
   - 已完成事项。
   - 指标变化。
   - 未解决风险。

### 10.5 报告输出

报告应支持：

1. 在 Onyx 管理后台查看。
2. 发送到 Slack、企业微信或 Email。
3. 下载为 Markdown 或 JSON。
4. 每条洞察都带 Onyx 和 Langfuse 深链。
5. 报告中的行动项可被标记状态：待处理、处理中、已完成、已忽略。

---

## 11. Feedback 闭环流程

### 11.1 标准闭环

本模块必须支持以下闭环：

1. 捕获：
   - Onyx 采集用户反馈、隐式反馈和检索反馈。
   - Langfuse 采集 trace、scores、cost、latency 和 prompt/model metadata。
2. 发现：
   - 通过 dashboard、异常检测和 LLM 报告识别问题。
3. 根因分析：
   - 从 Onyx 样本跳转到 chat session。
   - 从 Onyx 样本跳转到 Langfuse trace。
   - 查看 prompt、retrieval context、tool output、model 参数和 score。
4. 改进：
   - 调整 Prompt。
   - 补充 eval dataset。
   - 优化 RAG 检索、rerank、citation 或 connector。
   - 调整模型、temperature、max_tokens 或工具策略。
   - 修复产品交互或反馈采集问题。
5. 验证：
   - 通过 Langfuse datasets/experiments 或 Onyx A/B metadata 对比新旧版本。
   - 对比 score、feedback、成本、延迟和业务指标。
6. 发布：
   - 记录 release_version、prompt_version 或 experiment_id。
   - 上线后持续监控。
7. 沉淀：
   - 将失败样本加入 eval dataset。
   - 记录行动项结果和复盘结论。

### 11.2 失败样本池

本模块应维护可运营的失败样本池：

1. 自动进入失败样本池的条件：
   - 用户点踩。
   - `task_completion` 低于阈值。
   - `answer_groundedness` 低于阈值。
   - provider/tool error。
   - 高成本低质量。
2. 样本池字段至少包括：
   - 样本类型。
   - 关联 chat/session/message。
   - 关联 Langfuse trace。
   - 失败原因。
   - 业务维度。
   - 当前处理状态。
   - 是否加入 eval dataset。
3. 样本池应支持人工标记：
   - 真问题。
   - 误报。
   - 已修复。
   - 待补充数据。
   - 不处理。

### 11.3 实验与版本验证

每次 Prompt、RAG 或模型变更应尽量形成可验证实验：

1. 新旧版本必须带不同 `prompt_version`、`release_version` 或 `experiment_id`。
2. 实验样本应覆盖高频问题和失败样本池中的代表性问题。
3. 实验对比指标至少包括：
   - `task_completion`。
   - `retrieval_relevance`。
   - 用户反馈。
   - 成本。
   - latency。
4. 实验结论必须可回溯到样本和 trace。

---

## 12. 分阶段实施范围

### 12.1 第一阶段：可观测数据打底与反馈关联

目标：让现有 Langfuse 数据对业务分析可用。

范围：

1. 制定并落地 trace metadata 规范。
2. 补齐核心聊天生成 trace 的 `user_message_id`、`assistant_message_id`、`feature`、`assistant_id`、`llm_flow` 等字段。
3. 建立 Onyx feedback 与 Langfuse trace 的关联方式。
4. 将用户点赞、点踩和标准化原因写入 Langfuse score 或 comment。
5. 建立 Langfuse 基础 dashboard。
6. 在 Onyx Observability 页面增加业务入口说明和关键 dashboard 链接。

验收标准：

1. 负反馈样本可以从 Onyx feedback 跳转到 Langfuse trace。
2. Langfuse 中可以按 `feature`、`assistant_id`、`prompt_version`、`model_name` 过滤核心 trace。
3. `untagged_*` 占比可被看板监控。
4. 业务人员可以看到至少一套质量看板和一套成本/延迟看板。

### 12.2 第二阶段：业务洞察页与异常检测

目标：让业务人员不必进入 Langfuse 也能看到关键问题和行动入口。

范围：

1. 新增 Onyx “LLM 业务洞察”管理页。
2. 展示健康度总览、Top 风险、负反馈样本和深链。
3. 支持按时间、feature、assistant、model、prompt version 过滤。
4. 建立基础异常检测规则。
5. 支持 Slack、企业微信或 Email 告警。
6. 建立失败样本池。

验收标准：

1. 管理员可以在 Onyx 内看到过去 7 天质量、反馈、成本、延迟趋势。
2. 至少 5 类异常可以被检测并展示。
3. 每个异常都能下钻到样本 trace。
4. 失败样本可以被标记状态。

### 12.3 第三阶段：LLM 报告与 Eval 闭环

目标：让团队形成固定运营节奏，并能衡量优化效果。

范围：

1. 每周生成 LLM 观测报告。
2. 报告支持结构化 JSON 和 Markdown 输出。
3. 支持将失败样本加入 Langfuse dataset。
4. 支持基于 dataset/experiment 做 Prompt、RAG 或模型版本对比。
5. 支持行动项跟踪和 before/after 复盘。

验收标准：

1. 每周报告能总结 Top 3 问题、根因假设和行动建议。
2. 至少一种优化动作可以完成 before/after 验证。
3. 失败样本池中的样本可以进入 eval dataset。
4. 报告中的每个关键发现都有 trace 或 dashboard 链接支撑。

---

## 13. 管理后台页面建议

### 13.1 Observability 配置页增强

现有 Observability 页面继续用于工程配置验证，应增加：

1. Langfuse dashboard 链接配置。
2. Langfuse 项目环境说明。
3. 数据采集健康状态。
4. 最近 sample trace 发送结果。
5. `untagged_*` 提醒入口。

### 13.2 LLM 业务洞察页

新增页面用于日常业务使用：

1. 总览 tab：健康度、趋势、Top 风险。
2. 反馈 tab：点踩原因、反馈文本聚类、负反馈样本。
3. RAG tab：检索质量、引用点击、低相关样本。
4. 成本 tab：模型成本、功能成本、高成本低质量样本。
5. 实验 tab：prompt/model/release 版本对比。
6. 报告 tab：周报、行动项、复盘记录。

### 13.3 样本详情页

样本详情页应展示：

1. 用户问题。
2. 助手回答摘要。
3. 用户反馈。
4. 关联 documents/citations。
5. 质量 scores。
6. 成本和延迟。
7. 业务 metadata。
8. Onyx chat session 链接。
9. Langfuse trace 链接。
10. 加入 eval dataset 操作。

---

## 14. 权限与数据治理

### 14.1 权限

1. 只有具备管理权限的用户可以访问业务洞察页。
2. 只有更高权限用户可以查看原始 prompt、回答、检索上下文和用户反馈全文。
3. 普通运营角色可以查看脱敏后的聚合指标和样本摘要。
4. Langfuse 控制台本身必须由 Langfuse 或统一 IdP 独立控制访问权限。

### 14.2 脱敏

1. 默认不向业务报告输出完整 prompt、完整回答或完整 retrieved context。
2. 报告中展示的样本内容应截断并脱敏。
3. 对邮箱、手机号、token、authorization、private key、连接串等敏感内容必须脱敏。
4. 如果企业需要更严格的数据治理，应支持仅上报 metadata、usage、latency 和 scores，不上报 input/output。

### 14.3 数据保留

1. Langfuse trace 原始数据保留周期应可配置。
2. Onyx 内部聚合洞察可保留更长周期。
3. 失败样本池和 eval dataset 中的样本需要人工确认后长期保留。
4. 删除用户、会话或文档时，应评估关联 trace、feedback 和样本池数据的清理策略。

---

## 15. 与现有 AI 标签模块的关系

如果 AI 标签模块上线，本模块可为其提供质量反馈和运营洞察：

1. Taxonomy 生成、Summary、批量打标和健康自检相关 LLM 调用必须使用独立 `LLMFlow`。
2. AI 标签模块的失败样本应进入统一失败样本池。
3. 标签准确率、人工修改率、未匹配率和新增标签通过率可作为业务 score。
4. AI 标签相关 Prompt 版本变更应进入同一套 before/after 验证流程。

---

## 16. 非目标

MVP 阶段不做以下事项：

1. 不把 Langfuse UI iframe 嵌入 Onyx。
2. 不重写 Langfuse tracing、dashboard、dataset、experiment 或 prompt management 能力。
3. 不让 Onyx 前端接触 Langfuse secret key。
4. 不直接暴露 Langfuse ClickHouse 原始数据给普通业务用户。
5. 不自动根据报告修改 Prompt、RAG 或模型配置。
6. 不把隐式反馈直接当作用户满意度结论。
7. 不在样本不足时做强结论或强告警。

---

## 17. 风险与注意事项

1. Metrics API v2 当前按 Langfuse 官方文档说明为 Cloud-only，自托管部署需要保留替代数据路径。
2. 当前 Onyx 使用的 Langfuse Python SDK 版本与 Langfuse 平台版本需要持续验证兼容性。
3. 如果 trace input/output 包含敏感信息，业务看板和报告必须优先脱敏。
4. LLM-as-Judge 可能产生偏差，必须结合人工抽检。
5. 业务 metadata 过多会增加维护成本，应优先保证少量核心字段稳定。
6. 告警过多会导致团队忽略告警，MVP 应先少量高置信规则。
7. Feedback 同步 Langfuse 失败时，必须保证 Onyx 本地反馈不丢失。

---

## 18. 推荐运营节奏

1. 每日：
   - 查看负反馈、低 score 和异常提醒。
   - 处理高优先级失败样本。
2. 每周：
   - 阅读 LLM 观测报告。
   - 选择 Top 3 问题进入改进计划。
   - 将代表性失败样本加入 eval dataset。
3. 双周：
   - 复盘 Prompt、RAG 或模型改动的 before/after 数据。
   - 更新行动项状态。
4. 每季度：
   - 复盘 LLM 质量、成本和业务结果之间的关系。
   - 更新 score 定义、业务维度和 dashboard。

---

## 19. 参考资料

1. Langfuse Metrics API: https://langfuse.com/docs/metrics/features/metrics-api
2. Langfuse Custom Dashboards: https://langfuse.com/docs/metrics/features/custom-dashboards
3. Langfuse Evaluation and Scores: https://langfuse.com/docs/evaluation/overview
4. Langfuse Prompt Management: https://langfuse.com/docs/prompt-management/overview
5. Langfuse Datasets: https://langfuse.com/docs/evaluation/experiments/datasets
6. 当前项目 Langfuse 集成实施方案：`docs/architecture/langfuse-lknow.md`
7. 当前项目 Langfuse 本地验证文档：`docs/architecture/langfuse-local-validation.md`
