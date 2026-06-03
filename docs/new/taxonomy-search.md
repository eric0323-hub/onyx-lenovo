# Taxonomy Query 命中与 OpenSearch 标签过滤业务逻辑

## 1. 文档目的

本文档从 `AI 标签与企业 Taxonomy 知识治理模块` 中拆出检索相关逻辑，专门定义：

1. 用户 query 如何命中 Taxonomy 节点。
2. 命中的 Taxonomy 节点如何转换为检索过滤条件。
3. OpenSearch 检索时如何使用 Taxonomy 标签过滤。
4. 如何通过配置、隔离、降级和质量门槛避免影响现有检索效果。

本文档只描述业务规则和实现边界，不定义接口、数据库表结构、OpenSearch DSL 细节或具体算法实现。

---

## 2. 总体原则

1. Taxonomy 检索增强必须与现有检索框架解耦。
2. Taxonomy 做得不好时，不应影响现有检索效果。
3. Query 命中 Taxonomy 节点和 OpenSearch 使用标签过滤是两个独立阶段。
4. 阶段一可以先上线，只返回 Taxonomy 建议，不改变检索结果。
5. 阶段二必须在管理员显式开启后，才允许把 Taxonomy 命中结果加入 OpenSearch 过滤。
6. Taxonomy 过滤不得绕过现有 ACL、租户隔离、文档集、source、time 等过滤。
7. Taxonomy 过滤失败、超时、结果不足或配置关闭时，应回退到普通检索。
8. 所有自动命中和过滤行为都应可观测、可配置、可关闭。

---

## 3. 两阶段实现范围

### 3.1 阶段一：Query 命中 Taxonomy 节点

阶段一只做 query 与 Taxonomy 的匹配判断，输出候选节点、层级、置信度和建议动作。

阶段一不改变 OpenSearch 查询条件，不改变检索召回。

阶段一目标：

1. 支持管理员验证 Taxonomy 质量。
2. 支持前端展示“可能相关分类”。
3. 支持收集 query 到 Taxonomy 的命中日志。
4. 支持后续阶段二开启前的效果评估。

阶段一可独立交付。

### 3.2 阶段二：OpenSearch 使用 Taxonomy 标签过滤

阶段二在阶段一基础上，将高置信度或可接受置信度的 Taxonomy 命中结果转换为检索过滤条件。

阶段二目标：

1. 支持用户手动选择 Taxonomy 节点后过滤检索结果。
2. 支持 query 自动命中 Taxonomy 节点后进行软过滤或硬过滤。
3. 支持过滤结果不足时自动放宽。
4. 支持管理员配置是否启用、启用范围和阈值。

阶段二必须有完整 fallback，不得阻断普通检索。

---

## 4. 核心概念

### 4.1 Taxonomy 节点层级

Taxonomy 固定为三级：

1. 一级节点：业务域，例如“人力资源文档”。
2. 二级节点：主题域，例如“HR 政策”。
3. 三级叶子标签：文档最终绑定标签，例如“假期政策”。

文档最终只绑定三级叶子标签。

一级和二级节点参与检索时，必须展开为其下所有已生效三级叶子标签。

### 4.2 Query 命中

Query 命中是指系统根据用户输入识别出一个或多个可能相关的 Taxonomy 节点。

命中结果至少包含：

1. 节点 ID。
2. 节点名称。
3. 节点层级。
4. 完整路径。
5. 置信度。
6. 命中依据。
7. 建议动作：不使用、展示建议、软过滤、硬过滤。

### 4.3 Taxonomy 过滤

Taxonomy 过滤是指系统将命中的 Taxonomy 节点转换为三级叶子标签集合，并作为检索过滤条件传给 OpenSearch。

示例：

```text
命中二级节点：人力资源文档 > HR 政策
展开为三级叶子标签：
- 员工手册
- 假期政策
- 考勤制度
- 远程办公政策
```

### 4.4 硬过滤

硬过滤表示 OpenSearch 检索必须限制在命中的 Taxonomy 范围内。

硬过滤风险最高，只能在高置信度、Taxonomy 覆盖率充足、管理员允许时使用。

### 4.5 软过滤

软过滤表示系统可以先使用 Taxonomy 范围检索；若结果不足、分数过低或超时，则自动放宽到普通检索。

软过滤是推荐默认策略。

### 4.6 展示建议

展示建议表示系统只向用户展示“可能相关分类”，不影响 OpenSearch 查询。

展示建议适合阶段一或 Taxonomy 质量不稳定时使用。

---

## 5. 可配置项

建议将检索运行时配置放在 `/admin/configuration/chat-preferences` 的独立区块中，区块名称可为 `Taxonomy Search`。

Taxonomy 制作、节点维护、版本管理、影响分析和重分类任务不应放在 `Chat Preferences` 中，应放在独立 Taxonomy 管理页面。

### 5.1 总开关

```text
taxonomy_search_enabled
```

含义：是否允许 Taxonomy 参与检索流程。

关闭时：

1. Query 可以不执行 Taxonomy 命中。
2. 不得向 OpenSearch 添加 Taxonomy 过滤条件。
3. 现有检索链路保持不变。

### 5.2 检索模式

```text
taxonomy_search_mode
```

可选值：

1. `off`：完全关闭。
2. `manual_only`：仅用户手动选择 Taxonomy 节点时参与过滤。
3. `suggest_only`：query 自动命中只展示建议，不参与过滤。
4. `soft_filter_with_fallback`：query 自动命中后先过滤，结果不足时回退普通检索。
5. `hard_filter`：高置信度命中后直接过滤。

默认建议：

```text
manual_only 或 suggest_only
```

不建议默认开启 `hard_filter`。

### 5.3 作用范围

```text
taxonomy_search_apply_to
```

可选值：

1. `chat`：只作用于 Chat / RAG。
2. `search`：只作用于 Search UI。
3. `both`：Chat 和 Search UI 都作用。

默认建议：

```text
search
```

原因：Search UI 更适合展示和验证分类过滤，Chat 中硬过滤风险更高。

### 5.4 置信度阈值

```text
taxonomy_search_default_confidence_threshold
taxonomy_search_leaf_confidence_threshold
taxonomy_search_l2_confidence_threshold
taxonomy_search_l1_confidence_threshold
```

默认建议：

```text
default = 0.8
leaf = null
l2 = null
l1 = null
```

规则：

1. 若某层级没有单独配置阈值，则使用统一默认阈值。
2. 管理员可以分别配置三级、二级、一级阈值。
3. 一级命中范围更大，建议阈值不低于三级。

### 5.5 层级递进回退

```text
taxonomy_search_enable_hierarchy_fallback
```

含义：是否允许 query 在三级叶子置信度不足时，扩大到二级，再扩大到一级。

默认建议：

```text
true
```

### 5.6 一级和二级硬过滤权限

```text
taxonomy_search_allow_l2_hard_filter
taxonomy_search_allow_l1_hard_filter
```

默认建议：

```text
allow_l2_hard_filter = false
allow_l1_hard_filter = false
```

原因：

1. 二级和一级节点展开范围较大。
2. 二级和一级命中更适合软过滤或展示建议。
3. 默认禁止一级/二级硬过滤可以降低误伤召回的风险。

### 5.7 过滤结果最低要求

```text
taxonomy_search_min_results_for_filtered_search
```

含义：Taxonomy 过滤后，结果数低于该值时应自动放宽。

默认建议：

```text
5
```

### 5.8 最大叶子展开数量

```text
taxonomy_search_max_leaf_expansion_count
```

含义：一级或二级节点展开为三级叶子标签时，允许展开的最大叶子数量。

默认建议：

```text
100
```

超过该数量时：

1. 不应使用硬过滤。
2. 可以使用软过滤或展示建议。
3. 必须记录原因。

### 5.9 超时时间

```text
taxonomy_search_timeout_ms
```

含义：Query 命中 Taxonomy 节点的最大耗时。

默认建议：

```text
50 到 100 ms
```

超时时：

1. 不应阻断检索。
2. 不应向 OpenSearch 添加 Taxonomy 过滤条件。
3. 应回退普通检索。

### 5.10 质量门槛

```text
taxonomy_search_require_coverage_percent
taxonomy_search_require_version_confirmed
taxonomy_search_exclude_low_confidence_assignments
```

建议默认：

```text
require_version_confirmed = true
exclude_low_confidence_assignments = true
```

覆盖率阈值可由管理员配置。

---

## 6. 阶段一：Query 命中 Taxonomy 节点

### 6.1 输入

阶段一输入至少包括：

1. 用户 query。
2. 当前企业已生效 Taxonomy 版本。
3. Taxonomy 节点定义，包括名称、路径、说明、正例、反例、关键词、同义词。
4. 管理员配置。
5. 可选上下文：当前助手、知识库范围、用户手动筛选、会话上下文。

### 6.2 输出

阶段一输出 `TaxonomySearchDecision`。

至少包含：

1. 是否命中。
2. 命中节点 ID。
3. 命中节点层级。
4. 命中节点完整路径。
5. 置信度。
6. 候选节点列表。
7. 叶子展开结果。
8. 建议动作。
9. 不参与过滤的原因。
10. 是否超时。

示例：

```json
{
  "matched": true,
  "node_id": "HR-POLICY",
  "node_level": 2,
  "path": ["人力资源文档", "HR 政策"],
  "confidence": 0.84,
  "expanded_leaf_ids": ["HR-HANDBOOK", "HR-LEAVE", "HR-ATTENDANCE"],
  "recommended_action": "soft_filter",
  "reason": "leaf confidence was below threshold, l2 confidence passed"
}
```

### 6.3 命中顺序

Query 自动识别应采用层级递进逻辑：

1. 优先尝试命中三级叶子标签。
2. 若最佳三级叶子标签达到阈值，使用三级叶子标签作为命中节点。
3. 若三级叶子标签未达到阈值，尝试判断所属二级节点是否达到阈值。
4. 若二级节点达到阈值，使用二级节点作为命中节点，并展开其下三级叶子标签。
5. 若二级节点未达到阈值，尝试判断所属一级节点是否达到阈值。
6. 若一级节点达到阈值，使用一级节点作为命中节点，并展开其下三级叶子标签。
7. 若一级节点仍未达到阈值，则不使用 Taxonomy 过滤。

### 6.4 候选召回方式

阶段一不要求必须使用 LLM。

推荐使用轻量方式：

1. 关键词命中。
2. 同义词命中。
3. 预编译 regex 命中。
4. Query embedding 与 Taxonomy 节点 embedding 相似度。
5. Query 与节点卡片文本的全文匹配。

节点卡片文本应由节点信息构成：

```text
节点名称
完整路径
节点定义
适用范围
正例
反例
关键词
同义词
```

LLM 适合用于：

1. 离线生成 Taxonomy。
2. 离线评估 Taxonomy 质量。
3. 低置信度样本分析。
4. 管理员复核辅助。

不建议在每次 query 主链路中同步调用 LLM 做 Taxonomy 命中。

### 6.5 层级置信度计算

系统需要能输出三级、二级、一级的候选置信度。

二级置信度可以来自：

1. 二级节点自身定义与 query 的相似度。
2. 其下多个三级叶子候选的聚合分数。
3. 关键词或同义词直接命中二级节点。

一级置信度可以来自：

1. 一级节点自身定义与 query 的相似度。
2. 其下多个二级或三级候选的聚合分数。
3. 关键词或同义词直接命中一级节点。

具体算法不在本文档定义，但必须满足：

1. 输出可解释命中依据。
2. 输出可比较的置信度。
3. 支持按层级阈值判断。

### 6.6 阶段一动作决策

阶段一根据配置和置信度输出建议动作：

1. `none`：不命中，不参与后续处理。
2. `suggest`：只展示建议。
3. `soft_filter`：建议软过滤。
4. `hard_filter`：建议硬过滤。

若配置为 `suggest_only`，即使命中高置信度，也只能输出 `suggest`。

若配置为 `manual_only`，query 自动命中可不执行，或仅用于后台日志。

若配置为 `hard_filter`，仍必须满足质量门槛和置信度阈值。

---

## 7. 阶段二：OpenSearch 使用 Taxonomy 标签过滤

### 7.1 前置条件

阶段二只有在以下条件满足时才允许执行：

1. `taxonomy_search_enabled = true`。
2. `taxonomy_search_mode` 不是 `off` 或 `suggest_only`。
3. 当前企业存在已生效 Taxonomy 版本。
4. 命中的 Taxonomy 节点可以展开为至少一个已生效三级叶子标签。
5. 展开后的叶子数量不超过配置上限。
6. 当前 Taxonomy 质量门槛满足要求。
7. 当前请求所在场景符合 `taxonomy_search_apply_to` 配置。

任一条件不满足时，不得向 OpenSearch 添加 Taxonomy 过滤。

### 7.2 文档标签投影

为了复用现有 OpenSearch metadata tag 过滤，Taxonomy 打标结果应投影为文档 metadata。

建议至少投影：

```text
taxonomy_version = <version>
taxonomy_l1_id = <l1 id>
taxonomy_l2_id = <l2 id>
taxonomy_leaf_id = <leaf id>
taxonomy_path = <readable path>
```

文档绑定多个三级叶子标签时，应支持多值 metadata。

OpenSearch 检索时主要使用：

```text
taxonomy_leaf_id
```

一级和二级节点不直接作为文档最终绑定标签，但可用于展开叶子标签集合。

### 7.3 OpenSearch 过滤语义

Taxonomy 过滤应作为独立过滤组加入检索条件。

语义应为：

```text
AND (taxonomy_leaf_id in [leaf_a, leaf_b, leaf_c])
```

不能把自动命中的 Taxonomy 标签直接混入普通 metadata tags 的同一个 OR 组。

错误语义：

```text
AND (普通 metadata tag A OR taxonomy leaf X)
```

正确语义：

```text
AND (普通 metadata tag A OR 普通 metadata tag B)
AND (taxonomy leaf X OR taxonomy leaf Y)
```

原因：

1. 普通 metadata tags 和 Taxonomy 过滤是两个不同的收窄维度。
2. 混入同一个 OR 组可能扩大范围，违背“缩小检索范围”的目标。

### 7.4 与现有过滤的关系

Taxonomy 过滤必须与现有过滤共同生效：

1. ACL。
2. 租户隔离。
3. hidden。
4. source。
5. time。
6. document set。
7. assistant knowledge scope。
8. 用户手动选择的普通 tags。

Taxonomy 过滤只能缩小结果范围，不得扩大用户可见范围。

### 7.5 手动筛选

用户手动选择 Taxonomy 节点时：

1. 选择一级节点：展开为其下所有已生效三级叶子标签。
2. 选择二级节点：展开为其下所有已生效三级叶子标签。
3. 选择三级节点：直接使用该三级叶子标签。

手动筛选可以在 `manual_only` 模式下生效。

手动筛选应优先于 query 自动命中。

若用户已手动选择 Taxonomy 节点，系统不应再自动追加 query 命中节点，除非产品明确提供“扩展推荐分类”能力。

### 7.6 自动硬过滤

自动硬过滤只有在以下条件全部满足时才允许：

1. 配置模式允许硬过滤。
2. 命中节点置信度达到阈值。
3. 命中层级允许硬过滤。
4. 展开叶子数量不超过上限。
5. Taxonomy 覆盖率达到要求。
6. 当前节点下待重新打标文档比例低于阈值。
7. 当前请求没有用户手动选择冲突范围。

默认不建议允许一级或二级自动硬过滤。

### 7.7 自动软过滤

自动软过滤流程：

1. 根据 query 命中结果构造 Taxonomy 过滤条件。
2. 使用 Taxonomy 过滤执行一次检索。
3. 判断结果是否满足最低要求。
4. 若满足，返回过滤结果。
5. 若不满足，自动放宽到普通检索。
6. 返回时应记录曾尝试 Taxonomy 过滤，以及放宽原因。

结果不足判断至少包括：

1. 命中文档数量小于配置值。
2. 最高分低于系统可接受水平。
3. 没有可用于回答的文档片段。
4. OpenSearch 查询超时或失败。

### 7.8 展示建议

展示建议模式下：

1. 不向 OpenSearch 添加 Taxonomy 过滤。
2. 检索结果仍来自普通检索。
3. 前端可以展示“系统识别到可能相关分类”。
4. 用户可以手动点击建议分类后再次筛选。

---

## 8. 质量门槛

### 8.1 Taxonomy 覆盖率

Taxonomy 覆盖率指：当前可检索文档中，有多少文档已经绑定至少一个有效三级叶子标签。

公式：

```text
覆盖率 = 已绑定有效三级叶子标签的文档数 / 应参与 Taxonomy 治理的文档总数
```

有效三级叶子标签不包括：

1. 已删除标签。
2. 已停用标签。
3. 低置信度待确认标签。
4. 依赖已失效 Taxonomy 版本且需要重新打标的标签。
5. 打标失败或未匹配结果。

### 8.2 分层覆盖率

除全局覆盖率外，还应关注节点局部覆盖率。

例如 HR 分类覆盖率高，可以允许 HR 范围启用软过滤；财务分类覆盖率低，则财务范围不应启用自动过滤。

### 8.3 建议门槛

默认建议：

```text
覆盖率 < 50%：只允许 suggest_only。
50% <= 覆盖率 < 80%：允许 manual_only，不建议自动过滤。
80% <= 覆盖率 < 95%：允许 soft_filter_with_fallback。
覆盖率 >= 95%：可考虑高置信度 hard_filter。
```

具体阈值可由管理员调整。

### 8.4 待重新打标比例

若某个节点下大量文档处于待重新打标状态，该节点不应参与自动硬过滤。

系统应支持按节点计算：

```text
待重分类比例 = 节点下待重新打标文档数 / 节点下曾绑定文档数
```

超过配置阈值时：

1. 自动硬过滤禁用。
2. 可降级为软过滤或展示建议。
3. 应记录降级原因。

---

## 9. 解耦与隔离要求

### 9.1 模块隔离

建议将 Taxonomy 检索增强拆为独立模块：

```text
taxonomy_search_matcher
taxonomy_search_config
taxonomy_search_decision
taxonomy_filter_builder
```

搜索主流程只消费 `TaxonomySearchDecision`，不直接关心 Taxonomy 命中细节。

### 9.2 配置隔离

Taxonomy 检索增强必须受配置控制。

配置关闭时：

1. 不执行 query 自动命中，或只写后台日志。
2. 不修改 `IndexFilters`。
3. 不修改 OpenSearch 查询条件。
4. 不影响原有检索结果。

### 9.3 数据隔离

Taxonomy 本体、文档打标结果和 OpenSearch 检索投影应区分：

1. Taxonomy 本体用于治理和版本管理。
2. 文档打标结果用于审计、复核和重分类。
3. OpenSearch metadata tag 投影用于检索过滤。

不要把 Taxonomy 节点定义直接塞进 OpenSearch 查询链路。

### 9.4 语义隔离

Taxonomy 过滤不应复用普通 `tags` 的同一个 OR 语义组。

应在业务语义上区分：

1. 用户选择的普通 metadata tags。
2. 用户手动选择的 Taxonomy 节点。
3. Query 自动命中的 Taxonomy 节点。

三者都可以转换为 OpenSearch filter，但应保持独立 filter group。

---

## 10. 降级与回退

### 10.1 必须回退的场景

以下场景必须回退普通检索：

1. Taxonomy 检索配置关闭。
2. 当前企业没有生效 Taxonomy。
3. Query 命中超时。
4. Query 命中置信度不足。
5. 命中节点无法展开到有效三级叶子标签。
6. 展开叶子数量超过配置上限。
7. Taxonomy 覆盖率不满足要求。
8. 节点待重新打标比例过高。
9. OpenSearch 使用 Taxonomy 过滤后结果不足。
10. OpenSearch 查询失败。

### 10.2 回退后展示

回退后，系统可以展示：

1. 曾尝试命中的 Taxonomy 节点。
2. 未使用 Taxonomy 过滤的原因。
3. 用户可手动选择的建议分类。

回退不应表现为错误。

---

## 11. 日志与可观测性

系统应记录以下信息：

1. Query 文本。
2. 是否执行 Taxonomy 命中。
3. 候选节点。
4. 最终命中节点。
5. 命中层级。
6. 置信度。
7. 建议动作。
8. 实际动作。
9. 是否向 OpenSearch 添加 Taxonomy 过滤。
10. 展开的三级叶子标签数量。
11. 过滤前后结果数量。
12. 是否触发 fallback。
13. fallback 原因。
14. 耗时。

这些日志用于：

1. 判断 Taxonomy 是否适合参与检索。
2. 调整置信度阈值。
3. 发现低质量节点。
4. 评估自动过滤是否伤害召回。

---

## 12. 管理员可感知结果

管理员应能看到：

1. 当前 Taxonomy 检索模式。
2. 当前置信度阈值。
3. 当前 Taxonomy 覆盖率。
4. 各一级、二级节点的局部覆盖率。
5. Query 自动命中次数。
6. 自动过滤次数。
7. fallback 次数。
8. fallback 原因分布。
9. 高频命中节点。
10. 低置信度高频 query。

---

## 13. 交付拆分建议

### 13.1 第一步：Query 命中与建议

第一步交付范围：

1. Taxonomy 节点卡片生成。
2. Query 轻量命中 Taxonomy 节点。
3. 三级到二级到一级的层级递进逻辑。
4. 置信度阈值配置。
5. 输出 `TaxonomySearchDecision`。
6. 前端展示建议分类。
7. 日志与基础统计。

第一步不做：

1. 不改 OpenSearch 查询。
2. 不自动过滤检索结果。
3. 不影响原有检索效果。

### 13.2 第二步：OpenSearch 标签过滤

第二步交付范围：

1. 文档 Taxonomy 标签投影到 metadata。
2. 用户手动选择 Taxonomy 节点过滤。
3. Query 自动命中后的软过滤。
4. 过滤结果不足自动 fallback。
5. 配置 hard filter，但默认关闭。
6. 覆盖率与待重新打标比例门槛。
7. 过滤前后效果日志。

第二步上线前置条件：

1. 已有足够 Taxonomy 覆盖率。
2. Query 命中日志表现稳定。
3. 管理员明确开启。
4. fallback 能保证普通检索不被阻断。

---

## 14. 验收口径

第一步验收：

1. Query 可以返回候选 Taxonomy 节点、层级和置信度。
2. 三级置信度不足时可以回退到二级或一级。
3. 管理员可调整阈值。
4. `suggest_only` 模式不影响 OpenSearch 查询。
5. 命中超时或失败不影响普通检索。

第二步验收：

1. 手动选择一级、二级、三级节点均可转换为三级叶子标签过滤。
2. Query 自动命中后可按配置执行软过滤。
3. Taxonomy 过滤结果不足时可回退普通检索。
4. 关闭配置后不向 OpenSearch 添加 Taxonomy 过滤。
5. Taxonomy 过滤与 ACL、租户、文档集等现有过滤共同生效。
6. 普通 metadata tags 与 Taxonomy filters 的过滤语义保持隔离。
7. 管理员可看到过滤命中、fallback 和效果统计。
