# Langfuse Local Validation

This is the low-risk local workflow for reviewing the Onyx admin UI integration and the Langfuse traces it produces.

## Local URLs

- Onyx: `http://localhost:3000`
- Langfuse UI: `http://localhost:3001`

## Start Langfuse Locally

The default Docker Compose file includes an optional `langfuse` profile. It
starts Langfuse web, Langfuse worker, Postgres, ClickHouse, Redis, and a
Langfuse-specific MinIO instance with service names prefixed by `langfuse-`.
This keeps Langfuse infrastructure separate from Onyx's own database/cache/file
store while still sharing the same Docker network.

Enable the local stack in `deployment/docker_compose/.env`:

```env
COMPOSE_PROFILES=s3-filestore,langfuse
LANGFUSE_HOST=http://langfuse-web:3000
LANGFUSE_UI_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-local-onyx
LANGFUSE_SECRET_KEY=sk-lf-local-onyx
LANGFUSE_INIT_PROJECT_PUBLIC_KEY=pk-lf-local-onyx
LANGFUSE_INIT_PROJECT_SECRET_KEY=sk-lf-local-onyx
LANGFUSE_INIT_USER_EMAIL=admin@example.com
LANGFUSE_INIT_USER_PASSWORD=LangfuseLocal123!
```

Then start or recreate the services:

```bash
cd deployment/docker_compose
docker compose up -d langfuse-web langfuse-worker
docker compose up -d --force-recreate api_server background web_server nginx
```

If you use the dev override:

```bash
cd deployment/docker_compose
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d langfuse-web langfuse-worker
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate api_server background web_server nginx
```

The bundled profile initializes a local Langfuse organization/project and the
project API keys listed above. For production, replace every `LANGFUSE_*`
secret and prefer a separately managed Langfuse deployment.

Check local startup:

```bash
docker compose ps langfuse-web langfuse-worker
curl http://localhost:3001
```

`LANGFUSE_HOST` is the URL used by the API server and workers to send traces.
`LANGFUSE_UI_HOST` is only the browser link shown in the Onyx admin page. Do
not put `LANGFUSE_SECRET_KEY` in any frontend or `NEXT_PUBLIC_*` variable.

After changing these values, restart the API server and workers. Restarting
only the web server is not enough because the tracing processor is initialized
in the Python services.

## UI Review Flow

1. Start the `langfuse` compose profile.
2. Restart the Onyx API server and workers so `setup_tracing()` runs with the new keys.
3. Open `http://localhost:3001` and log in with the local Langfuse admin account if needed.
4. Open `http://localhost:3000/admin/performance/observability`.
5. Confirm the page shows public key, secret key, processor, and console URL as configured.
6. Click `Send Samples`.
7. Open Langfuse and check the Traces view.

Local Langfuse login:

- Email: `admin@example.com`
- Password: `LangfuseLocal123!`

If the `Send Samples` button is disabled, the status card should tell you which
part is missing. Common causes are missing keys, `LANGFUSE_UI_HOST` not set, or
the API server not restarted after adding credentials.

If clicking `Send Samples` shows `Langfuse tracing provider is not initialized`,
restart the API server and workers again and check the API server logs for
Langfuse initialization errors.

## Sample Data to Inspect

The `Send Samples` action creates two synthetic traces through the real Onyx tracing processor:

- `langfuse_local_sample_chat`
  - `flow=chat_response`
  - `session_id=langfuse-local-ui-review`
  - `model=gpt-5-mini`
  - input asks for Q2 renewal risk
  - output summarizes renewal risk and next action

- `langfuse_local_sample_indexing`
  - `flow=contextual_rag_chunk_context`
  - `session_id=langfuse-local-indexing-review`
  - `model=gpt-5-mini`
  - input describes chunk-context creation
  - output describes the chunk context

These samples do not call a real LLM. They only validate tracing export, Langfuse field mapping, and UI discoverability.

## What to Check in Langfuse

- Both traces appear within a short delay.
- The trace names are readable.
- `user_id` is populated.
- `session_id` is populated and filterable.
- `flow` is visible in model config / metadata.
- Input/output content is understandable and not too noisy.
- The generated usage values appear.

## Expected Onyx Admin Page State

Before keys are configured:

- Public key configured: off
- Secret key configured: off
- Processor initialized: off
- Console URL available: off unless `LANGFUSE_HOST` or `LANGFUSE_UI_HOST` is set
- `Send Samples`: disabled

After keys are configured and the API server has restarted successfully:

- Public key configured: on
- Secret key configured: on
- Processor initialized: on
- Console URL available: on
- `Send Samples`: enabled

When Onyx and Langfuse both run in Docker, the page should show a
separate-ingestion-url notice:

- Ingestion host: `http://langfuse-web:3000`
- Console URL: `http://localhost:3001`

## Minimal Rollback

Remove `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` from the API server and
workers, then restart those services. The Observability page will remain
available, but sample sending will be disabled and no Langfuse processor will
be initialized.
