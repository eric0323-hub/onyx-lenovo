# Onyx 外部聊天 Bot Gateway 统一接入技术方案

## 1. 文档目标

本文用于指导后续将 Onyx 现有 Slack / Discord bot 入口统一到一套可扩展的外部聊天 Bot Gateway 底座中，并为后续接入 Teams、飞书、钉钉、Telegram、QQ/OneBot、企业微信等平台提供稳定的工程标准。

目标不是新增一个临时 bot 进程，也不是把某个第三方 bot 框架整体嵌入 Onyx，而是建设 Onyx 自有的统一 bot 接入协议、运行时、数据库模型、管理 API 和前端入口。

设计原则：

- 现有 Slack / Discord 不能长期保留为遗产入口，必须迁移到统一底座。
- 后续所有平台必须通过同一套 adapter protocol 接入。
- 平台差异必须被隔离在 adapter、renderer 和 capability 层，不能污染核心 responder。
- 可以容忍短期功能 parity 不完整和部分 bug，但底座抽象必须稳定、通用、可二次开发。
- 优先复用 Onyx 已有 chat、persona、权限、租户、API key、日志、tracing、数据库和前端体系。

## 2. 当前 Onyx 现状

### 2.1 现有入口

当前 Onyx 已有两个外部聊天 bot 入口：

| 平台 | 入口进程 | 代码路径 | 特点 |
|---|---|---|---|
| Slack | `python onyx/onyxbot/slack/listener.py` | `backend/onyx/onyxbot/slack` | Socket Mode、多租户、Slack block、按钮、ephemeral、channel config、标准答案 |
| Discord | `python onyx/onyxbot/discord/client.py` | `backend/onyx/onyxbot/discord` | `discord.py` gateway、guild/channel config、注册命令、调用 Onyx chat API |

启动配置位于 `backend/supervisord.conf`：

```text
[program:slack_bot]
command=python onyx/onyxbot/slack/listener.py

[program:discord_bot]
command=python onyx/onyxbot/discord/client.py
```

这说明 Onyx 目前已经把聊天 bot 当作独立常驻进程处理，而不是主 FastAPI API server 的一部分。

### 2.2 当前架构问题

当前 Slack / Discord 是两套独立实现：

- 两套进程入口。
- 两套平台专用数据库表。
- 两套管理 API。
- 两套前端页面。
- 两套消息判断、上下文构建、回复渲染、错误处理和限流逻辑。
- `MessageOrigin` 中已有 `SLACKBOT`、`DISCORDBOT`，继续扩展会导致每接一个平台都要修改核心 enum。

现有专用表包括：

- `slack_bot`
- `slack_channel_config`
- `discord_bot_config`
- `discord_guild_config`
- `discord_channel_config`

如果继续按这个模式接入 Teams、飞书、钉钉、Telegram 等，平台数量越多，维护成本越高，二次开发会变成多套相似但不一致的代码。

### 2.3 当前可复用能力

尽管结构分散，现有实现仍然有很多值得复用的资产：

- Slack 的多租户 token 管理、Socket Mode 连接管理、Redis heartbeat / lock。
- Slack 的 channel config、allowlist、标准答案、按钮交互、ephemeral 回复经验。
- Discord 的 service API key 模式和通过 `/chat/send-chat-message` 调 Onyx API 的路径。
- Discord 的 guild/channel 注册、缓存刷新、thread context 处理。
- Onyx 现有 persona、document set、chat session、citation、feedback、API key、tenant DB session、加密凭证能力。

## 3. 外部框架调研

本节调研的目的不是选择一个框架直接替换 Onyx，而是判断哪些能力值得迁移、哪些框架适合成为 adapter 依赖、哪些只能作为架构参考。

### 3.1 opsdroid

官方定位：Python chat-ops bot framework。

核心概念：

- Connector 负责连接外部聊天平台或事件源。
- Connector 将平台原始事件转成框架内部消息对象。
- Connector 提供回复能力，把内部响应发回原平台。
- Skill / parser / matcher 负责业务逻辑。

官方 custom connector 文档中，connector 的核心生命周期是：

- `connect`
- `listen`
- `respond`

这与我们需要的 Gateway / Adapter 模型高度一致。

opsdroid 支持或曾支持的 connector 类型包括：

- Slack
- Microsoft Teams
- Telegram
- Websocket
- Webhook
- Matrix
- Shell
- 其他社区 connector

优点：

- Python 代码，理念接近目标架构。
- Connector 模型清晰，适合作为 Onyx adapter protocol 的设计参考。
- 平台接入与业务逻辑分离。
- 支持自定义 connector，便于研究其生命周期。

缺点：

- opsdroid 自带 config、skill、parser、database 生命周期。
- Onyx 已有自己的 chat API、persona、tenant、权限、DB、tracing、前端配置。直接嵌入 opsdroid core 会形成第二套运行时。
- opsdroid 的技能系统与 Onyx Agent / Skill / Tool 系统概念重叠，直接合并容易产生职责冲突。
- 平台 connector 的活跃程度和功能完整性需要逐一验证，不能假设全部生产可用。

结论：

opsdroid 适合作为 **架构参考和 adapter protocol 参考**，不适合作为 Onyx 的主 bot runtime 直接嵌入。

推荐迁移点：

- Connector 生命周期：`connect / listen / respond`。
- 平台事件标准化。
- 平台回复封装。
- 自定义 connector 扩展方式。

不推荐迁移点：

- opsdroid core。
- opsdroid skill / parser。
- opsdroid 配置系统。
- opsdroid 数据存储生命周期。

参考：

- https://opsdroid.dev/
- https://docs.opsdroid.dev/en/stable/connectors/index.html
- https://docs.opsdroid.dev/en/stable/connectors/custom.html

### 3.2 OpenClaw

官方定位：AI agent / bot 平台，强调 Gateway daemon 与 Channel Adapter。

根据公开文档和 README，OpenClaw 的模式大致是：

```text
Gateway daemon
  -> Channel Adapter
  -> Agent Core
  -> Skills / Memory / Tools
```

Channel Adapter 负责：

- 接收外部平台消息。
- 转成统一消息格式。
- 将回复渲染成平台格式，例如 Slack blocks、Telegram inline keyboard、Teams adaptive cards。

优点：

- Gateway + Channel Adapter 的目标形态非常接近本方案。
- 明确把平台差异隔离到 adapter / renderer。
- 作为产品形态参考价值高。

缺点：

- 不是 Onyx 当前技术栈的一部分。
- 与 Onyx Agent / Skill / Tool / RAG 能力重叠。
- 更适合作为参考产品，而不是代码依赖。

结论：

OpenClaw 适合作为 **目标产品形态和运行模型参考**。Onyx 应吸收其 Gateway daemon、Channel Adapter、platform renderer 思路，但不要整体引入。

参考：

- https://openclawdoc.com/docs/channels/overview/
- https://github.com/openclaw/openclaw

### 3.3 NoneBot2

官方定位：跨平台 Python bot framework。

核心概念：

- Driver：负责运行时与网络服务，例如 ASGI/FastAPI、HTTP、WebSocket。
- Adapter：平台协议适配层。
- Bot / Event / Message：平台抽象。
- Matcher / Plugin：业务处理层。

NoneBot2 的价值在于平台生态，尤其适合中文 IM 场景：

- QQ / OneBot
- 飞书
- 钉钉
- Telegram
- Discord
- 其他社区 adapter

优点：

- Python 生态，适合与 Onyx 后端栈整合。
- Adapter 生态丰富，尤其中文 IM 平台覆盖更好。
- 可以作为一个平台聚合 adapter，把多个平台事件统一接入 Onyx Gateway。
- 可以避免为飞书、钉钉、QQ 等平台从零实现协议。

缺点：

- NoneBot2 本身也有插件、matcher、运行时生命周期。
- 不应该让 NoneBot2 成为 Onyx 的总 bot 标准，否则 Onyx bot core 会被 NoneBot2 的插件模型绑定。
- 不同 adapter 的成熟度、维护状态、事件格式和平台能力不一致。
- Slack 支持不是 NoneBot2 官方生态重点，不适合用它替换现有 Slack。

结论：

NoneBot2 应作为 **Onyx Gateway 的一个 adapter implementation**，而不是 Gateway 本身。

建议定位：

```text
Onyx Gateway
  -> NoneBotAdapter
       -> FeishuAdapter
       -> DingTalkAdapter
       -> OneBotAdapter
       -> TelegramAdapter
```

参考：

- https://nonebot.dev/
- https://nonebot.dev/docs/2.4.4/api/adapters/
- https://nonebot.dev/docs/next/tutorial/store

### 3.4 Microsoft Teams 相关 SDK

Teams 接入必须单独看，因为 Microsoft 生态正在从 Bot Framework SDK 迁移到更新的 Agents / Teams SDK 路线。

候选：

| 方案 | 说明 | 适用性 |
|---|---|---|
| Bot Framework Python SDK | 传统 Teams bot 接入方式，基于 Activity / Connector 协议 | 技术可行，但长期风险较高 |
| Teams AI / Teams SDK | Microsoft Teams 侧更现代的 bot / agent SDK 路线 | 值得调研后优先考虑 |
| Microsoft 365 Agents SDK | Microsoft 推荐的新 agent 开发路径之一 | 后续演进方向，需要预留替换空间 |

风险：

- Microsoft 已说明 Bot Framework SDK 进入维护/归档状态，support tickets 在 2025-12-31 之后不再接受。
- Python SDK 的长期演进不确定。
- Teams 平台消息、Adaptive Card、OAuth、installation、tenant、channel/team/thread 语义较复杂。

结论：

Teams 必须通过 `TeamsAdapter` 隔离 SDK 选择，不能把 Bot Framework Python SDK 的类型泄漏到 Onyx core。

推荐策略：

- 初期如需快速落地，可以用 Bot Framework Python SDK 做 `TeamsAdapter` 的第一版。
- Adapter protocol 必须保持稳定，后续可以替换为 Teams SDK / Microsoft 365 Agents SDK。
- 出站回复统一用 Onyx `OutboundBotAction`，由 `TeamsRenderer` 转成 Adaptive Card 或普通文本。

参考：

- https://learn.microsoft.com/en-us/azure/bot-service/bot-service-overview?view=azure-bot-service-4.0
- https://learn.microsoft.com/en-us/microsoftteams/platform/teams-sdk/teams/sdk-comparison
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/what-are-bots

### 3.5 Slack SDK / Slack Bolt for Python

当前 Onyx Slack bot 使用 Slack SDK、Socket Mode、WebClient、Block Kit 等能力。

Slack 接入方式：

- Events API + HTTP endpoint。
- Socket Mode + WebSocket。
- Slack Bolt for Python，可封装事件、命令、action、middleware。
- slack_sdk，可底层控制 WebClient、SocketModeClient。

当前 Onyx 已有较多 Slack 专用能力：

- 多租户 Slack app token / bot token 管理。
- Socket Mode client 生命周期。
- Redis tenant lock 和 heartbeat。
- Slack channel config。
- Slack block buttons。
- ephemeral 回复。
- slash command。
- 标准答案。
- 反馈提醒。

结论：

Slack 必须迁入统一 Gateway，但不建议第一阶段改用 NoneBot2 或 opsdroid connector。更稳的方式是把现有 Slack 代码重构成 `SlackAdapter`，继续复用 Slack SDK。

迁移重点：

- `listener.py` 中连接管理逻辑迁到 `SlackAdapter`。
- 现有 Slack event parsing 迁到 `normalize_event`。
- 现有 Slack reply / block rendering 迁到 `SlackRenderer`。
- 现有 Slack channel config 迁到通用 DB 模型。
- button/action 等交互作为 `InboundBotEvent.event_type` 进入统一 core。

参考：

- https://slack.dev/python-slack-sdk/
- https://slack.dev/bolt-python/
- https://api.slack.com/apis/connections/socket

### 3.6 discord.py

当前 Onyx Discord bot 基于 `discord.py` 的 `commands.Bot`。

当前实现特点：

- 通过 Discord Gateway 长连接接收消息。
- 支持 guild 注册。
- 支持 channel sync。
- 支持 channel config。
- 收到消息后调用 Onyx `/chat/send-chat-message`。
- 使用 service API key 代表 bot 调用 Onyx API。

优点：

- 当前代码已经比较接近目标架构中的 adapter 模型。
- 业务逻辑相对 Slack 更少，迁移难度低。
- 可作为第一个真实平台 adapter 迁移对象。

缺点：

- 现有实现仍然耦合 Discord 类型和 DB 查询。
- 平台回复、上下文构建、应答判断没有统一抽象。

结论：

Discord 应作为第一个迁移到 Gateway 的现有平台。迁移完成后删除旧 `discord_bot` 进程入口。

参考：

- https://discordpy.readthedocs.io/

### 3.7 LangBot

LangBot 是一个 Python 为主的多平台 AI bot 项目，支持多种聊天平台和 LLM/RAG 能力。

优点：

- 多平台覆盖更接近产品化需求。
- 有管理面、插件、pipeline、平台适配等完整产品思路。
- 对飞书、钉钉、QQ、微信、Telegram、Discord、Slack 等平台覆盖有参考价值。

缺点：

- 它本身是完整 AI bot 平台，与 Onyx 的 LLM、RAG、Agent、插件、管理面明显重叠。
- 不适合整体嵌入 Onyx。
- 更适合作为平台覆盖、管理面和 adapter 组织方式的参考。

结论：

LangBot 可作为 **产品调研参考**，不作为依赖或直接移植目标。

参考：

- https://github.com/langbot-app/LangBot
- https://langbot.app/

## 4. 技术选型结论

综合调研后，推荐选型如下：

| 层级 | 推荐方案 | 原因 |
|---|---|---|
| Gateway runtime | Onyx 自研 | 需要深度绑定 Onyx tenant、persona、权限、DB、API key、tracing |
| Adapter protocol | 借鉴 opsdroid / OpenClaw | `connect / listen / respond` 和 Channel Adapter 模型成熟 |
| Slack adapter | 迁移现有 Slack SDK 实现 | 现有能力复杂，不能轻易替换 |
| Discord adapter | 迁移现有 discord.py 实现 | 当前实现清晰，适合作为首个迁移平台 |
| 多中文 IM 平台 | NoneBot2 adapter | 借力生态，不绑定核心 |
| Teams adapter | 独立 adapter，SDK 可替换 | 避免 Bot Framework Python SDK 长期风险 |
| 管理面参考 | LangBot / OpenClaw | 参考多平台配置和 adapter 展示，不直接嵌入 |

核心判断：

```text
不要引入一个外部 bot runtime。
要在 Onyx 内建立自己的 Bot Gateway 标准。
```

## 5. 目标架构

### 5.1 总体架构

```text
External Chat Platforms
  -> Slack / Discord / Teams / NoneBot2 / Future Adapters
  -> Onyx External Bot Gateway
  -> Unified Bot Core
  -> Onyx Chat API / Chat Engine
  -> LLM / Search / Persona / Tools
  -> Renderer
  -> Platform Reply
```

### 5.2 代码结构建议

```text
backend/onyx/onyxbot/
  gateway/
    service.py
    runtime.py
    registry.py
    config.py
    health.py
    metrics.py

  common/
    models.py
    adapter.py
    capabilities.py
    responder.py
    renderer.py
    api_client.py
    dedup.py
    context.py
    errors.py
    telemetry.py

  adapters/
    slack/
      adapter.py
      normalizer.py
      renderer.py
      client.py
      actions.py
      models.py

    discord/
      adapter.py
      normalizer.py
      renderer.py
      client.py
      commands.py
      models.py

    teams/
      adapter.py
      normalizer.py
      renderer.py
      client.py
      models.py

    nonebot/
      adapter.py
      normalizer.py
      renderer.py
      client.py
      models.py

    mock/
      adapter.py
      renderer.py
```

### 5.3 进程模型

最终只保留一个统一 bot 进程入口：

```text
[program:external_bot_gateway]
command=python onyx/onyxbot/gateway/service.py
stdout_logfile=/var/log/external_bot_gateway.log
redirect_stderr=true
autorestart=true
startretries=5
startsecs=60
```

旧入口需要迁移后删除：

```text
[program:slack_bot]
[program:discord_bot]
```

运行时内部按 bot instance 启动 adapter task：

```text
GatewayRuntime
  -> SlackAdapter instance task
  -> DiscordAdapter instance task
  -> TeamsAdapter instance task
  -> NoneBotAdapter instance task
```

为了降低单进程故障半径，service 也可以支持按平台或实例分片启动：

```bash
python onyx/onyxbot/gateway/service.py --platform slack
python onyx/onyxbot/gateway/service.py --platform discord
python onyx/onyxbot/gateway/service.py --instance-id 123
```

注意：这不是保留遗产。只要 adapter protocol、DB、admin API、responder 统一，物理进程是否拆分只是部署策略。

## 6. 核心协议设计

### 6.1 Adapter Protocol

```python
from collections.abc import AsyncIterator
from typing import Any, Protocol

from pydantic import BaseModel


class BotAdapter(Protocol):
    platform: BotPlatform

    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...

    async def health(self) -> AdapterHealth:
        ...

    async def listen(self) -> AsyncIterator[InboundBotEvent]:
        ...

    async def send(self, action: OutboundBotAction) -> None:
        ...

    def capabilities(self) -> BotCapabilities:
        ...

    @classmethod
    def credential_model(cls) -> type[BaseModel]:
        ...

    @classmethod
    def config_model(cls) -> type[BaseModel]:
        ...
```

### 6.2 Platform Enum

```python
class BotPlatform(str, Enum):
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    NONEBOT = "nonebot"
    LARK = "lark"
    DINGTALK = "dingtalk"
    TELEGRAM = "telegram"
    ONEBOT = "onebot"
    WECOM = "wecom"
    CUSTOM_WEBHOOK = "custom_webhook"
```

### 6.3 Inbound Event

```python
class InboundBotEvent(BaseModel):
    event_id: str
    event_type: BotEventType
    platform: BotPlatform

    tenant_id: str | None = None
    bot_instance_id: int | None = None
    workspace_id: str | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    message_id: str | None = None

    sender_id: str | None = None
    sender_display_name: str | None = None
    sender_email: str | None = None

    text: str | None = None
    mentions_bot: bool = False
    is_direct_message: bool = False
    raw_event: dict[str, Any] = {}

    attachments: list[BotAttachment] = []
    received_at: datetime
```

### 6.4 Outbound Action

```python
class OutboundBotAction(BaseModel):
    action_id: str
    action_type: BotActionType
    platform: BotPlatform

    bot_instance_id: int
    workspace_id: str | None
    channel_id: str | None
    thread_id: str | None
    message_id: str | None

    text: str | None = None
    blocks: list[BotBlock] = []
    citations: list[BotCitation] = []
    visibility: BotVisibility = BotVisibility.CHANNEL
    raw_payload: dict[str, Any] = {}
```

### 6.5 Capability Model

```python
class BotCapabilities(BaseModel):
    supports_threads: bool = False
    supports_ephemeral: bool = False
    supports_reactions: bool = False
    supports_buttons: bool = False
    supports_cards: bool = False
    supports_markdown: bool = True
    supports_channel_discovery: bool = False
    supports_user_lookup: bool = False
    supports_file_attachments: bool = False
    supports_streaming_update: bool = False
```

核心业务不能写：

```python
if platform == "slack":
    ...
```

而应该写：

```python
if capabilities.supports_ephemeral:
    ...
```

平台专用逻辑只能出现在 adapter / renderer 内部。

## 7. 核心业务流程

### 7.1 入站消息流程

```text
Adapter receives raw event
  -> normalize to InboundBotEvent
  -> dedup check
  -> resolve tenant / workspace / channel config
  -> should_respond
  -> build BotRequestContext
  -> call OnyxResponder
  -> get BotResponse
  -> render to OutboundBotAction
  -> adapter.send
```

### 7.2 应答判断

统一由 `ShouldRespondService` 处理：

- bot instance 是否启用。
- workspace 是否启用。
- channel 是否启用。
- 是否 direct message。
- 是否 require mention。
- 是否 thread-only。
- sender 是否在 allowlist。
- 是否命中特定 answer filter。
- 是否超过 rate limit。
- 是否重复事件。

平台 adapter 只提供事实，不做业务判断。例如：

- `mentions_bot=True`
- `is_direct_message=True`
- `thread_id=...`
- `sender_id=...`

### 7.3 Onyx Chat 调用

从 Discord 当前 `OnyxAPIClient` 抽出通用 client：

```python
class BotChatClient:
    async def send_message(
        self,
        tenant_id: str,
        api_key: str,
        message: str,
        persona_id: int | None,
        platform: BotPlatform,
        metadata: BotOriginMetadata,
    ) -> ChatFullResponse:
        ...
```

现有 `MessageOrigin` 建议新增：

```python
EXTERNAL_BOT = "external_bot"
```

并增加 metadata：

```json
{
  "platform": "slack",
  "workspace_id": "T123",
  "channel_id": "C123",
  "thread_id": "1710000000.000000"
}
```

如果短期不想改 chat request schema，可以先新增多个 enum：

- `TEAMSBOT`
- `LARKBOT`
- `DINGTALKBOT`
- `TELEGRAMBOT`

但这不是长期推荐方案。

### 7.4 出站渲染

统一 responder 输出平台无关响应：

```python
class BotResponse(BaseModel):
    answer: str
    citations: list[BotCitation]
    followup_actions: list[BotInteraction]
    error: BotError | None
```

各平台 renderer 负责转成平台格式：

| 平台 | Renderer 输出 |
|---|---|
| Slack | Markdown + Block Kit |
| Discord | Markdown + message embeds |
| Teams | Text + Adaptive Card |
| Telegram | Markdown / HTML + inline keyboard |
| 飞书 | Text / card |
| 钉钉 | Markdown / action card |

## 8. 数据库设计

### 8.1 新表设计

#### `external_bot_instance`

Bot 实例表。一个实例对应一个平台 app / bot token / adapter config。

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | 内部 ID |
| `platform` | str | `slack` / `discord` / `teams` / `nonebot` |
| `name` | str | 管理端显示名 |
| `enabled` | bool | 是否启用 |
| `credentials` | encrypted JSON | 平台凭证 |
| `adapter_config` | JSONB | 平台配置 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

#### `external_bot_workspace`

外部 workspace / guild / team / tenant 绑定表。

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | 内部 ID |
| `bot_instance_id` | FK | bot 实例 |
| `external_workspace_id` | str | Slack team id / Discord guild id / Teams team id |
| `external_workspace_name` | str | 展示名 |
| `tenant_id` | str | Onyx tenant |
| `enabled` | bool | 是否启用 |
| `registration_key` | str nullable | 注册绑定用 |
| `registered_at` | datetime nullable | 注册时间 |

#### `external_bot_channel`

Channel 级配置。

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | 内部 ID |
| `workspace_id` | FK | workspace |
| `external_channel_id` | str | 外部 channel id |
| `external_channel_name` | str | channel 名称 |
| `channel_type` | str | `channel` / `dm` / `thread` / `forum` |
| `enabled` | bool | 是否启用 |
| `persona_id` | FK nullable | 默认 persona |
| `require_bot_mention` | bool | 是否要求 @bot |
| `thread_only` | bool | 是否只在线程回复 |
| `visibility_config` | JSONB | allowlist、ephemeral 等 |
| `behavior_config` | JSONB | filters、response type 等 |

#### `external_bot_event_dedup`

事件去重表。

字段建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | 内部 ID |
| `platform` | str | 平台 |
| `event_id` | str | 平台事件 ID |
| `message_id` | str nullable | 平台消息 ID |
| `bot_instance_id` | int | bot 实例 |
| `processed_at` | datetime | 处理时间 |

唯一约束：

```text
(platform, bot_instance_id, event_id)
```

#### `external_bot_service_api_key`

可以不新建表，优先复用现有 `ApiKey` 表，用规范命名：

```text
external-bot-service:{platform}:{bot_instance_id}
```

### 8.2 旧表迁移

迁移映射：

| 旧表 | 新表 |
|---|---|
| `slack_bot` | `external_bot_instance(platform='slack')` |
| `slack_channel_config` | `external_bot_channel` |
| `discord_bot_config` | `external_bot_instance(platform='discord')` |
| `discord_guild_config` | `external_bot_workspace` |
| `discord_channel_config` | `external_bot_channel` |

建议分两阶段：

1. 双读迁移期：新 Gateway 只读新表，migration 将旧表数据复制到新表。
2. 删除遗产期：确认新 Gateway 稳定后，删除旧表、旧 API、旧前端页面、旧进程。

如果业务可以接受不可逆升级，也可以一次性迁移并删除旧入口。

## 9. 管理 API 设计

新增统一 router：

```text
backend/onyx/server/manage/external_bot/api.py
```

路由建议：

```text
GET    /admin/external-bots/platforms
GET    /admin/external-bots/instances
POST   /admin/external-bots/instances
GET    /admin/external-bots/instances/{id}
PATCH  /admin/external-bots/instances/{id}
DELETE /admin/external-bots/instances/{id}

GET    /admin/external-bots/instances/{id}/workspaces
POST   /admin/external-bots/instances/{id}/workspaces
PATCH  /admin/external-bots/workspaces/{workspace_id}
DELETE /admin/external-bots/workspaces/{workspace_id}

GET    /admin/external-bots/workspaces/{workspace_id}/channels
POST   /admin/external-bots/workspaces/{workspace_id}/channels/sync
PATCH  /admin/external-bots/channels/{channel_id}

GET    /admin/external-bots/instances/{id}/health
POST   /admin/external-bots/instances/{id}/test-message
```

注意：新 FastAPI API 不使用 `response_model`，按项目规范直接给函数返回类型标注。

错误处理必须使用 `OnyxError`，不直接抛 `HTTPException`。

## 10. 前端设计

### 10.1 入口整合

现有：

- `/admin/bots`：Slack Integration
- `/admin/discord-bot`：Discord Integration

目标：

```text
/admin/bot-integrations
```

页面结构：

```text
Bot Integrations
  -> Instances
  -> Platforms
  -> Workspaces
  -> Channels
  -> Health / Logs
```

平台作为 tab 或 filter，而不是单独 admin route：

- Slack
- Discord
- Teams
- NoneBot
- Custom Webhook

### 10.2 表单设计

平台通过后端返回 schema / metadata 渲染不同凭证表单：

```json
{
  "platform": "slack",
  "credential_fields": [
    {"key": "bot_token", "type": "secret", "required": true},
    {"key": "app_token", "type": "secret", "required": true},
    {"key": "user_token", "type": "secret", "required": false}
  ],
  "config_fields": [
    {"key": "socket_mode", "type": "boolean", "default": true}
  ]
}
```

这样后续新增平台不需要为每个平台单独做完整页面。

## 11. Adapter 迁移策略

### 11.1 DiscordAdapter 第一迁移

原因：

- 当前 Discord 代码较接近目标形态。
- 已经通过 Onyx API 回答问题。
- 平台能力相对简单。

迁移步骤：

1. 抽出 `BotChatClient`。
2. 创建 `DiscordAdapter`，复用 `discord.py` client。
3. 将 `should_respond` 改造成通用服务。
4. 将 `process_chat_message` 拆成 responder + renderer。
5. 将 Discord DB 查询替换为通用 external bot DB。
6. 删除 `discord_bot` supervisord program。

首版必须支持：

- guild 注册。
- channel sync。
- @bot 触发。
- thread context。
- persona override。
- 普通文本回复。
- citation markdown。

首版可暂缓：

- 复杂 embed。
- streaming update。
- 高级 slash command。

### 11.2 SlackAdapter 第二迁移

原因：

- Slack 功能复杂，应在 Gateway 底座通过 Discord 验证后迁移。
- 但不能长期保留为遗产，必须纳入统一 DB 和 runtime。

迁移步骤：

1. 保留 Slack SDK / Socket Mode。
2. 将 `SlackbotHandler` 拆成 `SlackAdapter` 与 `SlackConnectionManager`。
3. 将 Slack event parsing 迁到 `SlackNormalizer`。
4. 将 Slack block 回复迁到 `SlackRenderer`。
5. 将 `SlackChannelConfig` 数据迁到 `external_bot_channel`。
6. 将按钮 / action payload 标准化为 `InboundBotEvent`.
7. 删除 `slack_bot` supervisord program。

首版必须支持：

- Socket Mode。
- 普通消息。
- @bot 触发。
- DM。
- thread 回复。
- channel persona。
- 基础 citation。
- allowlist。

首版可暂缓：

- 标准答案。
- follow-up 按钮。
- feedback reminder。
- publish ephemeral。
- continue in web UI。

这些能力后续通过 `BotInteraction` 和 `OutboundBotAction` 补齐。

### 11.3 NoneBotAdapter

定位：

- 作为多平台 adapter aggregator。
- 优先接入中文 IM 生态。

实现建议：

```text
NoneBotAdapter
  -> receives NoneBot Event
  -> maps Event to InboundBotEvent
  -> uses platform field to preserve sub-platform
  -> calls Onyx Gateway responder
  -> maps OutboundBotAction to NoneBot send API
```

需要注意：

- NoneBot 子平台能力差异很大，必须通过 `BotCapabilities` 表示。
- 不要使用 NoneBot matcher/plugin 承载 Onyx 业务逻辑。
- NoneBot 只负责协议接入和 send/receive。

### 11.4 TeamsAdapter

定位：

- 独立 adapter。
- SDK 可替换。

初期实现：

- Bot Framework Python SDK 或 Teams webhook 接入。
- Activity -> InboundBotEvent。
- OutboundBotAction -> Teams text / Adaptive Card。

长期要求：

- SDK 类型不能出现在 common core。
- 如果迁移到 Microsoft 365 Agents SDK，只替换 `adapters/teams` 内部实现。

## 12. 运行时与可靠性

### 12.1 Runtime

`GatewayRuntime` 职责：

- 加载 enabled bot instances。
- 根据 platform 创建 adapter。
- 启动 adapter task。
- 监听配置变更。
- 优雅停止。
- 健康检查。
- 指标上报。

### 12.2 配置刷新

可选方案：

1. 定时 polling DB。
2. Redis pub/sub 通知。
3. 管理 API 更新后写 Redis version。

推荐第一版使用 polling，简单可靠：

```text
每 30 秒扫描 external_bot_instance.updated_at
变更后重启对应 adapter instance
```

后续再增加 Redis pub/sub。

### 12.3 分布式锁

多副本部署时，同一 bot instance 不能被多个 gateway 同时消费。

建议使用 Redis lease：

```text
external_bot_gateway:{bot_instance_id}:lock
```

规则：

- adapter 启动前获取 lease。
- 定期续租。
- 失去 lease 后停止 adapter。
- Gateway 退出时释放 lease。

Slack 当前已有 tenant lock / heartbeat 经验，可以迁移为通用 `AdapterLeaseManager`。

### 12.4 去重

外部平台经常会重试事件。必须实现去重：

```text
if event_id already processed:
    skip
```

去重层应支持：

- Redis 快速去重，TTL 1-7 天。
- PostgreSQL 持久记录，便于审计和调试。

### 12.5 限流

限流分三层：

- 平台入站限流：避免恶意刷消息。
- Onyx LLM 调用限流：保护成本。
- 平台出站限流：避免触发 Slack/Discord/Teams rate limit。

限流 key：

```text
tenant_id
bot_instance_id
workspace_id
channel_id
sender_id
```

## 13. 观测与运维

### 13.1 日志字段

所有 bot gateway 日志必须包含：

- `platform`
- `bot_instance_id`
- `tenant_id`
- `workspace_id`
- `channel_id`
- `thread_id`
- `event_id`
- `message_id`

### 13.2 Metrics

建议新增 Prometheus metrics：

```text
external_bot_active_instances
external_bot_events_total
external_bot_events_deduped_total
external_bot_responses_total
external_bot_errors_total
external_bot_adapter_restarts_total
external_bot_response_latency_seconds
external_bot_chat_api_latency_seconds
```

label：

```text
platform
tenant_id
bot_instance_id
event_type
error_code
```

注意 tenant label 高基数风险。生产环境可只保留 platform / instance，tenant 进入日志。

### 13.3 Health

每个 adapter 暴露：

```python
class AdapterHealth(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy", "stopped"]
    connected: bool
    last_event_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None
```

管理 API：

```text
GET /admin/external-bots/instances/{id}/health
```

## 14. 安全与权限

### 14.1 凭证

所有平台 token / secret 必须使用 Onyx 现有 `EncryptedString` 或等效加密字段存储。

禁止：

- 明文日志输出 token。
- 在前端返回未 mask token。
- 在 raw_event 中持久化敏感字段。

### 14.2 Onyx API 调用身份

每个 bot instance 使用 service API key 调 Onyx API。

API key 命名：

```text
external-bot-service:{platform}:{bot_instance_id}
```

role 使用最小权限，原则上只允许 chat 相关 API。

### 14.3 用户身份映射

初期可以不强制将外部用户映射为 Onyx user，但必须保留字段：

- external_user_id
- display_name
- email
- platform

后续可扩展：

- Slack user email -> Onyx user。
- Teams AAD user id -> Onyx user。
- 飞书 open_id / union_id -> Onyx user。

### 14.4 权限边界

Bot channel config 必须控制：

- 哪些 channel 可以触发。
- 使用哪个 persona。
- 使用哪些 document set。
- 是否需要 @bot。
- 哪些用户或用户组可触发。

不要让外部聊天平台绕过 Onyx 现有 persona / document set / access control。

## 15. 测试策略

### 15.1 Unit Tests

适合：

- normalizer。
- renderer。
- capability 判断。
- should_respond。
- dedup key。
- config schema validation。

示例：

```text
backend/tests/unit/onyx/onyxbot/gateway/test_should_respond.py
backend/tests/unit/onyx/onyxbot/adapters/slack/test_normalizer.py
backend/tests/unit/onyx/onyxbot/adapters/discord/test_renderer.py
```

### 15.2 External Dependency Unit Tests

适合：

- DB CRUD。
- API key 创建。
- Redis lease。
- service API client。

### 15.3 Integration Tests

适合：

- MockAdapter -> Gateway -> Chat API -> Response。
- DB migration 后 Slack/Discord 配置可读。
- 多租户 instance lease。

### 15.4 Playwright Tests

适合：

- `/admin/bot-integrations` 页面。
- 新增 bot instance。
- channel 配置。
- health 状态展示。

## 16. 分阶段实施计划

### Phase 0: 技术验证

目标：

- 不迁移现有 Slack/Discord。
- 建立 common models、adapter protocol、MockAdapter。
- 跑通 Gateway -> Onyx chat API -> Mock reply。

交付：

- `onyxbot/common`
- `onyxbot/gateway`
- `MockAdapter`
- 基础 unit tests。

### Phase 1: 通用 DB 与 Admin API

目标：

- 新增 external bot 通用表。
- 新增管理 API。
- 新增 migration。

交付：

- `external_bot_instance`
- `external_bot_workspace`
- `external_bot_channel`
- `external_bot_event_dedup`
- CRUD tests。

### Phase 2: Discord 迁移

目标：

- Discord 迁入 Gateway。
- 删除旧 `discord_bot` 进程入口。

交付：

- `DiscordAdapter`
- Discord 配置迁移。
- Discord 前端入口迁移到 Bot Integrations。
- 保留核心功能。

验收：

- Discord guild 可注册。
- channel 可同步。
- bot 可回复。
- persona override 生效。
- 旧 `discord_bot` 不再启动。

### Phase 3: Slack 迁移

目标：

- Slack 迁入 Gateway。
- 删除旧 `slack_bot` 进程入口。

交付：

- `SlackAdapter`
- Slack 配置迁移。
- Slack channel config 迁移。
- Slack 基础消息/DM/thread/@bot 能力。

验收：

- Slack Socket Mode 正常连接。
- channel persona 生效。
- allowlist 生效。
- thread 回复正常。
- 旧 `slack_bot` 不再启动。

### Phase 4: NoneBot2 接入

目标：

- 通过 NoneBot2 接入第一批新平台。

建议平台顺序：

1. Telegram 或 OneBot，用于验证基础消息模型。
2. 飞书。
3. 钉钉。

验收：

- 新平台无需改 responder。
- 新平台只新增 adapter config / renderer。

### Phase 5: Teams 接入

目标：

- 实现 TeamsAdapter。
- 支持文本回复和 Adaptive Card。

验收：

- Teams channel 触发 bot。
- persona 生效。
- citation 正常显示。
- SDK 类型不泄漏到 common core。

### Phase 6: 高级能力补齐

补齐：

- Slack buttons。
- standard answers。
- feedback reminder。
- continue in web UI。
- streaming response update。
- file attachments。
- user identity mapping。
- platform-specific rich cards。

## 17. 风险清单

| 风险 | 影响 | 缓解 |
|---|---|---|
| Slack 功能复杂，迁移容易丢功能 | Slack 用户体验短期下降 | 分阶段 parity，先保核心功能 |
| 单 Gateway 进程故障影响多平台 | 可用性下降 | 支持按 platform / instance 分片启动 |
| NoneBot2 adapter 成熟度不一 | 新平台不稳定 | 每个平台单独验收，adapter 隔离 |
| Teams SDK 路线变化 | 后续维护成本 | TeamsAdapter 隔离 SDK |
| 通用模型过度抽象 | 开发复杂 | MVP 只支持 message/reply/thread/citation |
| DB migration 影响现有配置 | 升级风险 | 先复制迁移，保留回滚窗口 |
| 平台能力差异太大 | 核心逻辑出现平台判断 | 强制 capability / renderer 层隔离 |

## 18. 可靠性验证补充

本节记录进一步调研和小范围本地验证结果，用于判断方案是否具备工程落地可靠性。

### 18.1 Onyx 当前依赖与运行时验证

本地 `.venv` 使用 Python 3.11.12，与项目 `pyproject.toml` 中 `requires-python = ">=3.11"` 和 `tool.ty.environment.python-version = "3.11"` 对齐。

当前 Onyx 已安装并可导入的相关依赖：

| 依赖 | 当前版本 | 验证结论 |
|---|---:|---|
| `pydantic` | 2.11.7 | 可用于统一 bot message / config 模型 |
| `aiohttp` | 3.13.4 | 可用于异步 Onyx API client 和部分 adapter |
| `fastapi` | 0.133.1 | 可用于 webhook 类 adapter 或管理 API |
| `discord.py` / `discord-py` | 2.4.0 | 当前 Discord bot 已使用，适合迁移为 `DiscordAdapter` |
| `slack-sdk` | 3.20.2 | 当前 Slack bot 已使用，`SocketModeClient` / `WebClient` 可导入 |

额外确认：

- `slack_sdk.socket_mode.SocketModeClient` 可导入，构造函数支持 `app_token`、`web_client`、`auto_reconnect_enabled`、`concurrency`、message/error/close listeners。
- `slack_sdk.web.WebClient` 可导入，构造函数支持 `token`、`timeout`、`team_id`、`retry_handlers`。
- `discord.ext.commands.Bot` 可导入，构造函数要求 `command_prefix` 和 `intents`，与现有 `OnyxDiscordClient` 一致。
- `SendMessageRequest` 当前可以构造非流式 bot 调用 payload，现有 `origin` 只能使用 `slackbot` / `discordbot` / `api` 等枚举值，后续需要新增 `external_bot` 或 metadata 扩展。
- 当前 DB 模型确认存在旧表：`slack_bot`、`slack_channel_config`、`discord_bot_config`、`discord_guild_config`、`discord_channel_config`。

验证结论：

现有 Onyx 依赖已经足够支撑自研 Gateway 底座的第一阶段实现。Slack / Discord 不需要先更换 SDK，迁移风险主要来自业务逻辑拆分和 DB migration，不来自基础依赖缺失。

### 18.2 候选框架依赖解析验证

使用 `uv pip install --dry-run` 和项目 `backend/requirements/default.txt` 作为 constraints，分别验证候选依赖在 Python 3.11 下的解析情况。

验证命令形态：

```bash
uv pip install --dry-run \
  --target /private/tmp/onyx_bot_gateway_deps_<name> \
  --python ./.venv/bin/python \
  --default-index https://pypi.org/simple \
  -c backend/requirements/default.txt \
  <package>
```

结果：

| 依赖 | 解析结果 | 关键观察 |
|---|---|---|
| `nonebot2` | 通过 | 解析到 `nonebot2==2.5.0`，保留 Onyx pinned `pydantic==2.11.7` |
| `botbuilder-core` | 通过 | 解析到 `botbuilder-core==4.17.1`，保留 Onyx pinned `msal==1.34.0`、`requests==2.33.0` |
| `opsdroid` | 通过 | 在 Python 3.11 下解析到 `opsdroid==0.31.0`，保留 Onyx pinned `aiohttp==3.13.4` |

重要细节：

- 如果不显式使用项目 `.venv` 的 Python，`uv` 可能使用系统 Python 3.12。`opsdroid` 的旧版本在 Python 3.12 build 环境下可能触发 `configparser.SafeConfigParser` 相关构建失败。因此后续验证和 CI 必须显式使用项目 Python 3.11。
- 如果不使用 Onyx constraints，解析器会将部分依赖升级到不同版本，例如 `pydantic`、`aiohttp`、`msal` 等。这不代表冲突，但说明若直接新增依赖必须通过项目 constraints / lock 流程管理。
- `opsdroid` 会带入较多与 Onyx 无关的依赖，例如 notebook/nbconvert 相关包，不适合作为生产核心依赖整体加入。

验证结论：

NoneBot2 和 Bot Framework Python SDK 作为 adapter 内部依赖具备依赖层面可行性。opsdroid 也能在 Python 3.11 + Onyx constraints 下解析和安装，但它的依赖面较宽，进一步支持“不整体嵌入 opsdroid core，只借鉴其 connector 模型”的建议。

### 18.3 临时安装与核心类导入验证

为确认 dry-run 之外的可导入性，已将 `opsdroid`、`nonebot2`、`botbuilder-core` 临时安装到 `/private/tmp/onyx_bot_gateway_probe`，不写入项目 `.venv`，不修改 `pyproject.toml`。

验证对象：

| 框架 | 核心对象 | 结果 |
|---|---|---|
| opsdroid | `opsdroid.connector.Connector` | 可导入，存在 `connect`、`listen`、`respond`、`disconnect` 方法 |
| opsdroid | `opsdroid.message.Message` | 可导入，构造签名为 `text, user, room, connector, raw_message=None` |
| NoneBot2 | `nonebot.adapters.Adapter` | 可导入，存在 `_call_api`、`get_name`、`bot_connect`、`bot_disconnect` 等核心抽象 |
| NoneBot2 | `Bot` / `Event` / `Message` | 可导入，可作为 NoneBotAdapter 的边界模型参考 |
| Bot Framework | `ActivityHandler` | 可导入，存在 `on_turn`、`on_message_activity`、`on_members_added_activity` |
| Bot Framework | `TurnContext` | 可导入，存在 `send_activity` |
| Bot Framework | `Activity` | 可导入，适合作为 Teams raw activity 输入 |

验证结论：

三个框架的核心抽象与本文设计的 adapter 边界一致：

- opsdroid 证明 `connect / listen / respond / disconnect` 生命周期是可行的 Python bot connector 抽象。
- NoneBot2 适合作为一个二级 adapter runtime，把多平台 `Event` 映射到 Onyx `InboundBotEvent`。
- Bot Framework 的 `ActivityHandler / TurnContext / Activity` 能被隔离在 `TeamsAdapter` 内部。

### 18.4 Gateway Protocol 最小 PoC

已在临时文件 `/private/tmp/onyx_bot_gateway_poc.py` 做本地最小 PoC。该 PoC 不连接真实平台，不调用真实 Onyx API，只验证核心协议闭环。

PoC 覆盖：

- `BotAdapter` protocol。
- `InboundBotEvent` / `OutboundBotAction`。
- `BotCapabilities`。
- `GatewayRuntime`。
- 去重逻辑。
- channel config 解析。
- mention / DM 应答判断。
- capability-based renderer。
- Slack / Discord / Teams 三个 mock adapter 同时进入同一 core。

执行：

```bash
./.venv/bin/python /private/tmp/onyx_bot_gateway_poc.py
```

输出：

```text
POC_OK
{'slack_sent': 1, 'discord_sent': 1, 'teams_sent': 1, 'deduped_slack_duplicate': True, 'discord_ignored_non_mention': True, 'teams_card_rendered': True}
```

验证点：

| 验证点 | 结果 |
|---|---|
| 同一 runtime 可处理多个平台 adapter | 通过 |
| Slack duplicate event 可被通用 deduper 忽略 | 通过 |
| Discord 未 @bot 且非 DM 的消息可由通用 core 忽略 | 通过 |
| Discord DM 可绕过 require mention | 通过 |
| Slack 支持 thread 时保留 thread id | 通过 |
| Discord 不支持 thread 时 renderer 自动降级 | 通过 |
| Teams 支持 cards 时 renderer 输出 card payload | 通过 |
| persona_id 可从通用 channel config 传入 responder | 通过 |

PoC 结论：

本文提出的 `Adapter -> InboundBotEvent -> Core -> Responder -> Renderer -> OutboundBotAction -> Adapter.send` 链路具备可实现性，且平台差异可以通过 capability 和 renderer 隔离。下一步真实实现时应把 PoC 的内存组件替换为 Onyx DB、Redis dedup / lease、真实 BotChatClient 和真实平台 adapter。

### 18.5 验证后的方案调整

基于验证结果，对方案做如下强化：

1. `opsdroid` 继续只作为架构参考，不建议加入生产依赖。原因不是不可用，而是依赖面和运行时重叠较大。
2. `NoneBot2` 可以作为后续 adapter 依赖引入，但必须隔离在 `adapters/nonebot`，不要让 matcher/plugin 模型进入 Onyx core。
3. `botbuilder-core` 在依赖层面可行，但 Teams adapter 必须保持 SDK 可替换。
4. Gateway 第一阶段不需要引入任何新第三方框架，可先用现有 `pydantic`、`aiohttp`、`slack-sdk`、`discord.py` 实现 Slack/Discord 统一。
5. 依赖验证必须使用项目 Python 3.11，避免系统 Python 3.12 对部分旧包造成误判。

## 19. 决策建议

最终建议：

1. 建设 Onyx 自有 `external_bot_gateway`，不直接嵌入 opsdroid / OpenClaw / LangBot。
2. 借鉴 opsdroid 的 connector 生命周期和 OpenClaw 的 Gateway + Channel Adapter 产品形态。
3. 把 Slack / Discord 作为第一批标准 adapter 迁移，不能长期保留旧入口。
4. 把 NoneBot2 作为一个 adapter，用于快速接入中文 IM 和社区平台。
5. Teams 独立 adapter，SDK 可替换，避免绑定 Bot Framework Python SDK。
6. 统一 DB、API、前端、进程入口、message origin 和 telemetry。

推荐最终状态：

```text
external_bot_gateway
  -> SlackAdapter
  -> DiscordAdapter
  -> TeamsAdapter
  -> NoneBotAdapter
  -> CustomWebhookAdapter
       -> UnifiedBotCore
       -> OnyxResponder
       -> PlatformRenderer
```

这个方案工程量比新增平台更大，但能从根上解决二次开发和多平台扩展问题。它应被视为一次 bot 子系统重构，而不是单个平台集成任务。
