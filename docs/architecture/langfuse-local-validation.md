# Langfuse Local Validation

This is the low-risk local workflow for reviewing the Onyx admin UI integration and the Langfuse traces it produces.

## Local URLs

- Onyx: `http://localhost:3000`
- Langfuse UI: `http://localhost:3001`

## Start Langfuse Locally

Keep the first local validation run independent from the Onyx Docker Compose
stack. This makes the integration easy to turn off and avoids coupling Onyx
stability to Langfuse while you review the UI.

Recommended local flow:

1. Start Langfuse from the official Docker Compose example in a separate
   directory.
2. Publish the Langfuse web service on host port `3001`.
3. Open `http://localhost:3001`, create the first admin account, create a
   project, and copy that project's public and secret API keys.

Use the official Langfuse self-hosting Docker Compose documentation for the
exact compose file and required Langfuse infrastructure variables. The Onyx
integration only needs the final Langfuse UI URL and project keys.

If Onyx runs in Docker and Langfuse runs on the host, configure Onyx with:

```env
LANGFUSE_HOST=http://host.docker.internal:3001
LANGFUSE_UI_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

If Onyx backend runs directly on the host, `LANGFUSE_HOST=http://localhost:3001` is fine.

`LANGFUSE_HOST` is the URL used by the API server and workers to send traces.
`LANGFUSE_UI_HOST` is only the browser link shown in the Onyx admin page. Do
not put the Langfuse secret key in any frontend or `NEXT_PUBLIC_*` variable.

After changing these values, restart the API server and any workers you want to
trace. In local Docker, restarting only the web server is not enough because
the tracing processor is initialized in the Python services.

## UI Review Flow

1. Start Langfuse locally and create a project.
2. Copy the project public and secret keys into the Onyx API server and worker environment.
3. Restart the API server and workers so `setup_tracing()` runs with the new keys.
4. Open `http://localhost:3000/admin/performance/observability`.
5. Confirm the page shows public key, secret key, processor, and console URL as configured.
6. Click `Send Samples`.
7. Open Langfuse and check the Traces view.

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

When Onyx runs in Docker and Langfuse runs on the host, the page should show a
separate-ingestion-url notice:

- Ingestion host: `http://host.docker.internal:3001`
- Console URL: `http://localhost:3001`

## Minimal Rollback

Remove `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` from the API server and
workers, then restart those services. The Observability page will remain
available, but sample sending will be disabled and no Langfuse processor will
be initialized.
