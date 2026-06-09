from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class ExternalRetrievalAdapterType(str, Enum):
    HTTP_JSON = "http_json"
    ONTOLOGY = "ontology"


class ExternalRetrievalAuthType(str, Enum):
    NONE = "none"
    BEARER = "bearer"
    API_KEY_HEADER = "api_key_header"
    BASIC = "basic"


class ExternalRetrievalRequestMode(str, Enum):
    SIMPLE = "simple"
    STANDARD = "standard"
    CUSTOM_TEMPLATE = "custom_template"


class ExternalRetrievalCallStrategy(str, Enum):
    ORIGINAL_QUERY_ONCE = "original_query_once"
    SEMANTIC_QUERY_ONCE = "semantic_query_once"
    PER_EXPANDED_QUERY = "per_expanded_query"


class ExternalRetrievalAuthConfig(BaseModel):
    type: ExternalRetrievalAuthType = ExternalRetrievalAuthType.NONE
    token: str | None = None
    api_key_header: str | None = None
    api_key: str | None = None
    username: str | None = None
    password: str | None = None


class ExternalRetrievalConfig(BaseModel):
    endpoint: str
    method: str = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    request_mode: ExternalRetrievalRequestMode = ExternalRetrievalRequestMode.SIMPLE
    request_template: dict[str, Any] | None = None
    result_path: str | None = None
    field_mapping: dict[str, list[str]] = Field(default_factory=dict)
    max_content_chars: int = 6000
    score_scale: float | None = None
    allow_localhost: bool = False
    strict_result_validation: bool = False

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str) -> str:
        normalized = value.upper()
        if normalized != "POST":
            raise ValueError("External retrieval MVP only supports POST.")
        return normalized

    @field_validator("max_content_chars")
    @classmethod
    def validate_max_content_chars(cls, value: int) -> int:
        if value < 100:
            raise ValueError("max_content_chars must be at least 100.")
        return value


class ExternalRetrievalSourceConfig(BaseModel):
    id: int | None = None
    name: str
    description: str | None = None
    adapter_type: ExternalRetrievalAdapterType = ExternalRetrievalAdapterType.HTTP_JSON
    enabled: bool = False
    auth: ExternalRetrievalAuthConfig = Field(default_factory=ExternalRetrievalAuthConfig)
    config: ExternalRetrievalConfig
    timeout_ms: int = 3000
    max_results: int = 10
    source_weight: float = 0.6
    min_confidence: float | None = None
    call_strategy: ExternalRetrievalCallStrategy = (
        ExternalRetrievalCallStrategy.ORIGINAL_QUERY_ONCE
    )

    @field_validator("timeout_ms")
    @classmethod
    def validate_timeout_ms(cls, value: int) -> int:
        if value < 100:
            raise ValueError("timeout_ms must be at least 100.")
        return value

    @field_validator("max_results")
    @classmethod
    def validate_max_results(cls, value: int) -> int:
        if value < 1 or value > 50:
            raise ValueError("max_results must be between 1 and 50.")
        return value

    @field_validator("source_weight")
    @classmethod
    def validate_source_weight(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("source_weight must be greater than 0.")
        return value

    @field_validator("min_confidence")
    @classmethod
    def validate_min_confidence(cls, value: float | None) -> float | None:
        if value is not None and (value < 0 or value > 1):
            raise ValueError("min_confidence must be between 0 and 1.")
        return value


class ExternalRetrievalRequest(BaseModel):
    query: str
    limit: int
    document_set_names: list[str] | None = None
    user_id: UUID | None = None
    tenant_id: str | None = None
    request_id: str | None = None


class ExternalRetrievalTestRequest(BaseModel):
    query: str
    limit: int = 5
    include_raw_response: bool = False


class ExternalRetrievalInvalidResult(BaseModel):
    index: int
    reason: str
    available_fields: list[str]


class NormalizedExternalRetrievalResult(BaseModel):
    index: int
    title: str
    content: str
    url: str | None = None
    score: float
    confidence: float | None = None
    source_id: str | None = None
    result_id: str | None = None
    canonical_key: str | None = None
    fact_key: str | None = None
    dedupe_key: str
    content_fingerprint: str
    document_id: str
    updated_at: datetime | None = None
    metadata: dict[str, str | list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ExternalRetrievalTestResult(BaseModel):
    success: bool
    latency_ms: int | None = None
    normalized_results: list[NormalizedExternalRetrievalResult] = Field(
        default_factory=list
    )
    invalid_results: list[ExternalRetrievalInvalidResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_response: Any | None = None
    error_code: str | None = None
    message: str | None = None

