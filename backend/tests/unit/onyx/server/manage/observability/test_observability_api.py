from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from onyx.error_handling.exceptions import OnyxError
from onyx.main import get_application
from onyx.server.manage.observability import api
from onyx.tracing.framework import set_trace_processors
from onyx.tracing.framework.processor_interface import TracingProcessor
from onyx.tracing.framework.span_data import GenerationSpanData
from onyx.tracing.framework.spans import Span
from onyx.tracing.framework.traces import Trace


class RecordingTracingProcessor(TracingProcessor):
    def __init__(self) -> None:
        self.ended_traces: list[Trace] = []
        self.ended_generation_spans: list[GenerationSpanData] = []
        self.flush_count = 0

    def on_trace_start(self, trace: Trace) -> None:
        pass

    def on_trace_end(self, trace: Trace) -> None:
        self.ended_traces.append(trace)

    def on_span_start(self, span: Span[Any]) -> None:
        pass

    def on_span_end(self, span: Span[Any]) -> None:
        if isinstance(span.span_data, GenerationSpanData):
            self.ended_generation_spans.append(span.span_data)

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        self.flush_count += 1


def test_observability_router_is_registered() -> None:
    application = get_application()
    paths = {getattr(route, "path", "") for route in application.routes}

    assert "/admin/observability/langfuse/status" in paths
    assert "/admin/observability/langfuse/sample-traces" in paths


def test_get_langfuse_status_uses_distinct_ui_host() -> None:
    with (
        patch.object(api, "LANGFUSE_PUBLIC_KEY", "public"),
        patch.object(api, "LANGFUSE_SECRET_KEY", "secret"),
        patch.object(api, "LANGFUSE_HOST", "http://host.docker.internal:3001"),
        patch.object(api, "LANGFUSE_UI_HOST", "http://localhost:3001"),
        patch.object(
            api, "get_initialized_tracing_providers", return_value=["langfuse"]
        ),
    ):
        status = api.get_langfuse_status()

    assert status.enabled is True
    assert status.tracing_provider_initialized is True
    assert status.host == "http://host.docker.internal:3001"
    assert status.ui_host == "http://localhost:3001"
    assert status.using_distinct_ui_host is True


def test_get_langfuse_status_falls_back_to_ingestion_host() -> None:
    with (
        patch.object(api, "LANGFUSE_PUBLIC_KEY", "public"),
        patch.object(api, "LANGFUSE_SECRET_KEY", "secret"),
        patch.object(api, "LANGFUSE_HOST", "http://localhost:3001"),
        patch.object(api, "LANGFUSE_UI_HOST", ""),
        patch.object(api, "get_initialized_tracing_providers", return_value=[]),
    ):
        status = api.get_langfuse_status()

    assert status.enabled is True
    assert status.tracing_provider_initialized is False
    assert status.ui_host == "http://localhost:3001"
    assert status.using_distinct_ui_host is False


def test_send_sample_traces_requires_langfuse_credentials() -> None:
    with (
        patch.object(api, "LANGFUSE_PUBLIC_KEY", ""),
        patch.object(api, "LANGFUSE_SECRET_KEY", ""),
    ):
        with pytest.raises(OnyxError):
            api.send_langfuse_sample_traces(user=MagicMock())


def test_send_sample_traces_requires_initialized_provider() -> None:
    with (
        patch.object(api, "LANGFUSE_PUBLIC_KEY", "public"),
        patch.object(api, "LANGFUSE_SECRET_KEY", "secret"),
        patch.object(api, "get_initialized_tracing_providers", return_value=[]),
    ):
        with pytest.raises(OnyxError):
            api.send_langfuse_sample_traces(user=MagicMock())


def test_send_sample_traces_flushes_provider() -> None:
    provider = MagicMock()
    user = MagicMock()
    user.id = 7

    with (
        patch.object(api, "LANGFUSE_PUBLIC_KEY", "public"),
        patch.object(api, "LANGFUSE_SECRET_KEY", "secret"),
        patch.object(
            api, "get_initialized_tracing_providers", return_value=["langfuse"]
        ),
        patch.object(api, "get_trace_provider", return_value=provider),
    ):
        response = api.send_langfuse_sample_traces(user=user)

    assert response.sent is True
    assert response.trace_count == 2
    provider.force_flush.assert_called_once()


def test_send_sample_traces_emits_expected_review_data() -> None:
    recorder = RecordingTracingProcessor()
    user = MagicMock()
    user.id = 7

    set_trace_processors([recorder])
    try:
        with (
            patch.object(api, "LANGFUSE_PUBLIC_KEY", "public"),
            patch.object(api, "LANGFUSE_SECRET_KEY", "secret"),
            patch.object(
                api, "get_initialized_tracing_providers", return_value=["langfuse"]
            ),
        ):
            response = api.send_langfuse_sample_traces(user=user)
    finally:
        set_trace_processors([])

    assert response.sent is True
    assert recorder.flush_count == 1

    traces_by_name = {trace.name: trace for trace in recorder.ended_traces}
    assert set(traces_by_name) == {
        "langfuse_local_sample_chat",
        "langfuse_local_sample_indexing",
    }

    chat_trace_metadata = getattr(
        traces_by_name["langfuse_local_sample_chat"], "metadata"
    )
    assert chat_trace_metadata["chat_session_id"] == "langfuse-local-ui-review"
    assert chat_trace_metadata["source"] == "admin_observability_sample"
    assert chat_trace_metadata["user_id"] == "7"

    indexing_trace_metadata = getattr(
        traces_by_name["langfuse_local_sample_indexing"], "metadata"
    )
    assert (
        indexing_trace_metadata["chat_session_id"] == "langfuse-local-indexing-review"
    )
    assert indexing_trace_metadata["connector"] == "file"

    spans_by_flow = {
        str(span.model_config["flow"]): span for span in recorder.ended_generation_spans
    }
    assert set(spans_by_flow) == {
        api.LLMFlow.CHAT_RESPONSE.value,
        api.LLMFlow.CONTEXTUAL_RAG_CHUNK_CONTEXT.value,
    }

    chat_span = spans_by_flow[api.LLMFlow.CHAT_RESPONSE.value]
    assert chat_span.model == "gpt-5-mini"
    assert chat_span.usage == {
        "prompt_tokens": 42,
        "completion_tokens": 38,
        "total_tokens": 80,
    }
    assert chat_span.input is not None
    assert "Q2 renewal risk" in str(chat_span.input[0]["content"])

    indexing_span = spans_by_flow[api.LLMFlow.CONTEXTUAL_RAG_CHUNK_CONTEXT.value]
    assert indexing_span.model == "gpt-5-mini"
    assert indexing_span.usage == {
        "prompt_tokens": 55,
        "completion_tokens": 31,
        "total_tokens": 86,
    }
    assert indexing_span.input is not None
    assert "chunk context" in str(indexing_span.input[0]["content"])
