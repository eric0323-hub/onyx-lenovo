# PROJECT KNOWLEDGE BASE

This file provides guidance to AI agents when working with code in this repository.

## KEY NOTES

- If you run into any missing python dependency errors, try running your command with `source .venv/bin/activate` \
  to assume the python venv.
- You should assume that all Onyx services are running. To verify, you can check the `backend/log` directory to
  make sure we see logs coming out from the relevant service.
- To connect to the Postgres database, use: `docker exec -it onyx-relational_db-1 psql -U postgres -c "<SQL>"`
- When making calls to the backend, always go through the frontend. E.g. make a call to `http://localhost:3000/api/persona` not `http://localhost:8080/api/persona`
- Put ALL db operations under the `backend/onyx/db` / `backend/ee/onyx/db` directories. Don't run queries
  outside of those directories.

## Project Overview

**Onyx** (formerly Danswer) is an open-source Gen-AI and Enterprise Search platform that connects to company documents, apps, and people. It features a modular architecture with both Community Edition (MIT licensed) and Enterprise Edition offerings.

### Background Workers (Celery)

Onyx uses Celery for asynchronous task processing with multiple specialized workers:

#### Worker Types

1. **Primary Worker** (`celery_app.py`)
   - Coordinates core background tasks and system-wide operations
   - Handles connector management, document sync, pruning, and periodic checks
   - Runs with 4 threads concurrency
   - Tasks: connector deletion, vespa sync, pruning, LLM model updates, user file sync

2. **Docfetching Worker** (`docfetching`)
   - Fetches documents from external data sources (connectors)
   - Spawns docprocessing tasks for each document batch
   - Implements watchdog monitoring for stuck connectors
   - Configurable concurrency (default from env)

3. **Docprocessing Worker** (`docprocessing`)
   - Processes fetched documents through the indexing pipeline:
     - Upserts documents to PostgreSQL
     - Chunks documents and adds contextual information
     - Embeds chunks via model server
     - Writes chunks to Vespa vector database
     - Updates document metadata
   - Configurable concurrency (default from env)

4. **Light Worker** (`light`)
   - Handles lightweight, fast operations
   - Tasks: vespa metadata sync, connector deletion, doc permissions upsert, checkpoint cleanup, index attempt cleanup
   - Higher concurrency for quick tasks

5. **Heavy Worker** (`heavy`)
   - Handles resource-intensive operations
   - Tasks: connector pruning, document permissions sync, external group sync, CSV generation
   - Runs with 4 threads concurrency

6. **Monitoring Worker** (`monitoring`)
   - System health monitoring and metrics collection
   - Monitors Celery queues, process memory, and system status
   - Single thread (monitoring doesn't need parallelism)
   - Cloud-specific monitoring tasks

7. **User File Processing Worker** (`user_file_processing`)
   - Processes user-uploaded files
   - Handles user file indexing and project synchronization
   - Configurable concurrency

8. **Beat Worker** (`beat`)
   - Celery's scheduler for periodic tasks
   - Uses DynamicTenantScheduler for multi-tenant support
   - Schedules tasks like:
     - Indexing checks (every 15 seconds)
     - Connector deletion checks (every 20 seconds)
     - Vespa sync checks (every 20 seconds)
     - Pruning checks (every 20 seconds)
     - Monitoring tasks (every 5 minutes)
     - Cleanup tasks (hourly)

#### Key Features

- **Thread-based Workers**: All workers use thread pools (not processes) for stability
- **Tenant Awareness**: Multi-tenant support with per-tenant task isolation. There is a
  middleware layer that automatically finds the appropriate tenant ID when sending tasks
  via Celery Beat.
- **Task Prioritization**: High, Medium, Low priority queues
- **Monitoring**: Built-in heartbeat and liveness checking
- **Failure Handling**: Automatic retry and failure recovery mechanisms
- **Redis Coordination**: Inter-process communication via Redis
- **PostgreSQL State**: Task state and metadata stored in PostgreSQL

#### Important Notes

**Defining Tasks**:

- Always use `@shared_task` rather than `@celery_app`
- Put tasks under `background/celery/tasks/` or `ee/background/celery/tasks`
- Never enqueue a task without an expiration. Always supply `expires=` when
  sending tasks, either from the beat schedule or directly from another task. It
  should never be acceptable to submit code which enqueues tasks without an
  expiration, as doing so can lead to unbounded task queue growth.

**Defining APIs**:
When creating new FastAPI APIs, do NOT use the `response_model` field. Instead, just type the
function.

**Task Time Limits**:
Since all tasks are executed in thread pools, the time limit features of Celery are silently
disabled and won't work. Timeout logic must be implemented within the task itself.

NOTE: Always make sure everything is strictly typed (both in Python and Typescript).

## Architecture Overview

### Technology Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Alembic, Celery
- **Frontend**: Next.js 15+, React 18, TypeScript, Tailwind CSS
- **Database**: PostgreSQL with Redis caching
- **Search**: Vespa vector database
- **Auth**: OAuth2, SAML, multi-provider support
- **AI/ML**: LangChain, LiteLLM, multiple embedding models

### Directory Structure

```
backend/
├── onyx/
│   ├── auth/                    # Authentication & authorization
│   ├── chat/                    # Chat functionality & LLM interactions
│   ├── connectors/              # Data source connectors
│   ├── db/                      # Database models & operations
│   ├── document_index/          # Vespa integration
│   ├── federated_connectors/    # External search connectors
│   ├── llm/                     # LLM provider integrations
│   └── server/                  # API endpoints & routers
├── ee/                          # Enterprise Edition features
├── alembic/                     # Database migrations
└── tests/                       # Test suites

web/
├── src/app/                     # Next.js app router pages
├── src/components/              # Reusable React components
└── src/lib/                     # Utilities & business logic
```

## Frontend Standards

Frontend standards for the `web/` projects live in `web/AGENTS.md`.

### Desktop-Only Frontend Development (Mandatory)

- For every frontend implementation, UI redesign, layout adjustment, or visual polish task, use the `frontend-design` skill before making code changes.
- For frontend tasks, explicitly state that the `frontend-design` skill is being used before implementation.
- Unless the user explicitly requests mobile support in the current task, all frontend work is desktop-web only.
- Desktop layouts should work well from 1200px to 1920px. Use 1440px wide as the default validation viewport unless a task specifies another desktop width.
- Do not design, implement, or QA mobile layouts.
- Do not add phone/tablet breakpoints such as `sm:` or mobile-first layout variants.
- Desktop-only breakpoint behavior for large screens is allowed when it improves 1200px+ layouts.
- Do not add mobile-specific navigation, compact phone layouts, or touch-only interaction patterns.
- Do not spend time checking mobile screenshots, mobile responsiveness, or mobile usability.
- Existing responsive code may be left alone unless it interferes with the requested desktop behavior.
- New UI should prioritize desktop information density, precise alignment, stable component sizing, and clear visual hierarchy.
- For substantial redesigns, briefly outline the layout and component structure before editing. For small UI changes, implement directly.

### Core UI Rules (Mandatory)

- **Always prioritize the Opal Design System**:
  - New components and pages → `web/lib/opal/src/` (especially `@opal/components`, `@opal/layouts`)
  - Production components → `web/src/refresh-components/`
  - **Never** use legacy components in `web/src/components/` (being phased out)
  - Card-style components → `web/src/sections/cards/`

- **Typography & Layout Consistency** (to prevent messy layouts):
  - **Always** use the Opal `Text` component for all text (with `font` and `color` props). **Never** use naked `<div>`, `<p>`, `<h1>`, `<span>`, etc.
  - Default `size` variant for all components is `"md"` unless explicitly required otherwise.
  - Use Opal layout primitives: `Content`, `ContentAction`, `IllustrationContent`, `SettingsLayouts`, etc.
  - Strictly follow the project's spacing scale, typography hierarchy, and design tokens.

- **Size & Visual Balance**:
  - Maintain consistent component sizing and spacing.
  - Ensure proper visual hierarchy and proportional sizing across the page.
  - Validate desktop layout quality only; do not perform mobile-first responsive checks unless explicitly requested.

- **Other Strict Rules**:
  - Icons: Only use icons from `web/src/icons/`. Do not use lucide/react-icons or other external libraries.
  - Do not use manual `dark:` Tailwind modifiers (except for logo icons).
  - Buttons must use Opal `Button` with correct `variant`, `prominence`, and `size`.
  - New settings/admin pages must be wrapped in `SettingsLayouts`.

## Logs

Use `backend/log/<service_name>_debug.log` to inspect service logs. All Onyx services
(api_server, web_server, celery_X) tail their logs to this file.

## Security Considerations

- Never commit API keys or secrets to repository
- Use encrypted credential storage for connector credentials
- Follow RBAC patterns for new features
- Implement proper input validation with Pydantic models
- Use parameterized queries to prevent SQL injection

## AI/LLM Integration

- Multiple LLM providers supported via LiteLLM
- Configurable models per feature (chat, search, embeddings)
- Streaming support for real-time responses
- Token management and rate limiting
- Custom prompts and agent actions

### Tracing — every LLM invocation must be tagged

Every LLM, embedding, rerank, image-generation, voice (STT/TTS), and intent-classification call must open a generation span tagged with a value from the `LLMFlow` registry in `backend/onyx/tracing/flows.py`. Use one of:

- `llm_generation_span(llm=..., flow=LLMFlow.X, input_messages=...)` for calls going through an `LLM` subclass.
- `traced_llm_call(flow=LLMFlow.X, model=..., provider=..., input_messages=...)` for direct provider SDK / `litellm` / model_server HTTP calls that bypass the `LLM` abstraction.

Rules:

1. Add a new `LLMFlow` enum value before instrumenting a new operation. Don't pass raw strings.
2. Flow tags name the **operation** (e.g. `IMAGE_EDIT`, `RERANK`) — not the provider. Provider lives in `model_config["model_provider"]`.
3. The auto-wrap fallback in `onyx/llm/tracing_wrap.py` emits `LLMFlow.UNTAGGED_INVOKE` / `UNTAGGED_STREAM` for calls that reach `LLM.invoke` / `LLM.stream` without an explicit span. These sentinels are visible in dashboards and indicate missing instrumentation — fix the call site, don't rely on the fallback.

## Best Practices

In addition to the other content in this file, best practices for contributing
to the codebase can be found in the "Engineering Best Practices" section of
`CONTRIBUTING.md`. Understand its contents and follow them.
