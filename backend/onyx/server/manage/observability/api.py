from fastapi import APIRouter
from fastapi import Depends

from onyx.auth.permissions import require_permission
from onyx.configs.app_configs import LANGFUSE_HOST
from onyx.configs.app_configs import LANGFUSE_PUBLIC_KEY
from onyx.configs.app_configs import LANGFUSE_SECRET_KEY
from onyx.configs.app_configs import LANGFUSE_UI_HOST
from onyx.db.enums import Permission
from onyx.db.models import User
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.manage.observability.models import LangfuseSampleTraceResponse
from onyx.server.manage.observability.models import LangfuseStatusResponse
from onyx.tracing.flows import LLMFlow
from onyx.tracing.framework.create import generation_span
from onyx.tracing.framework.create import trace
from onyx.tracing.framework.setup import get_trace_provider
from onyx.tracing.setup import get_initialized_tracing_providers

admin_router = APIRouter(prefix="/admin/observability")


def _langfuse_ui_host() -> str | None:
    host = LANGFUSE_UI_HOST or LANGFUSE_HOST
    return host or None


def _langfuse_enabled() -> bool:
    return bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)


@admin_router.get("/langfuse/status")
def get_langfuse_status(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> LangfuseStatusResponse:
    ui_host = _langfuse_ui_host()
    host = LANGFUSE_HOST or None
    return LangfuseStatusResponse(
        enabled=_langfuse_enabled(),
        tracing_provider_initialized="langfuse" in get_initialized_tracing_providers(),
        public_key_configured=bool(LANGFUSE_PUBLIC_KEY),
        secret_key_configured=bool(LANGFUSE_SECRET_KEY),
        host=host,
        ui_host=ui_host,
        using_distinct_ui_host=bool(host and ui_host and host != ui_host),
    )


@admin_router.post("/langfuse/sample-traces")
def send_langfuse_sample_traces(
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> LangfuseSampleTraceResponse:
    if not _langfuse_enabled():
        raise OnyxError(
            OnyxErrorCode.ENV_VAR_GATED,
            "Langfuse credentials are not configured.",
        )
    if "langfuse" not in get_initialized_tracing_providers():
        raise OnyxError(
            OnyxErrorCode.SERVICE_UNAVAILABLE,
            "Langfuse tracing provider is not initialized. Restart the API server and workers after setting credentials.",
        )

    sample_chat_session_id = "langfuse-local-ui-review"
    metadata = {
        "chat_session_id": sample_chat_session_id,
        "user_id": str(user.id),
        "source": "admin_observability_sample",
        "tenant_id": "local",
    }

    with trace(
        "langfuse_local_sample_chat",
        group_id=sample_chat_session_id,
        metadata=metadata,
    ):
        with generation_span(
            input=[
                {
                    "role": "user",
                    "content": "Summarize Q2 renewal risk for Acme in two bullets.",
                }
            ],
            output=[
                {
                    "role": "assistant",
                    "content": (
                        "Acme shows moderate renewal risk because usage dropped "
                        "after the billing admin change. Next step: schedule a "
                        "success review and confirm the SSO rollout owner."
                    ),
                }
            ],
            model="gpt-5-mini",
            model_config={
                "model_provider": "openai",
                "flow": LLMFlow.CHAT_RESPONSE.value,
                "temperature": 0.2,
                "max_tokens": 256,
            },
            usage={
                "prompt_tokens": 42,
                "completion_tokens": 38,
                "total_tokens": 80,
            },
        ):
            pass

    with trace(
        "langfuse_local_sample_indexing",
        metadata={
            **metadata,
            "chat_session_id": "langfuse-local-indexing-review",
            "connector": "file",
        },
    ):
        with generation_span(
            input=[
                {
                    "role": "user",
                    "content": (
                        "Create chunk context for a customer renewal note "
                        "covering adoption blockers and next steps."
                    ),
                }
            ],
            output=[
                {
                    "role": "assistant",
                    "content": (
                        "This chunk belongs to a customer renewal workspace "
                        "and highlights adoption risk, owner changes, and "
                        "follow-up actions."
                    ),
                }
            ],
            model="gpt-5-mini",
            model_config={
                "model_provider": "openai",
                "flow": LLMFlow.CONTEXTUAL_RAG_CHUNK_CONTEXT.value,
                "temperature": 0.0,
                "max_tokens": 192,
            },
            usage={
                "prompt_tokens": 55,
                "completion_tokens": 31,
                "total_tokens": 86,
            },
        ):
            pass

    get_trace_provider().force_flush()

    return LangfuseSampleTraceResponse(
        sent=True,
        trace_count=2,
        message="Sample Langfuse traces sent. Refresh the Langfuse Traces view.",
    )
