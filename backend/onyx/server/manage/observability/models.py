from pydantic import BaseModel


class LangfuseStatusResponse(BaseModel):
    enabled: bool
    tracing_provider_initialized: bool
    public_key_configured: bool
    secret_key_configured: bool
    host: str | None
    ui_host: str | None
    using_distinct_ui_host: bool


class LangfuseSampleTraceResponse(BaseModel):
    sent: bool
    trace_count: int
    message: str
