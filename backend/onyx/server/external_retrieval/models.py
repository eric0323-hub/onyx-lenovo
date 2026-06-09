from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import Field

from onyx.external_retrieval.models import ExternalRetrievalAdapterType
from onyx.external_retrieval.models import ExternalRetrievalAuthConfig
from onyx.external_retrieval.models import ExternalRetrievalCallStrategy
from onyx.external_retrieval.models import ExternalRetrievalConfig
from onyx.external_retrieval.models import ExternalRetrievalTestRequest
from onyx.external_retrieval.models import ExternalRetrievalTestResult


class ExternalRetrievalDocumentSetView(BaseModel):
    id: int
    name: str


class ExternalRetrievalSourceUpsertRequest(BaseModel):
    name: str
    description: str | None = None
    adapter_type: ExternalRetrievalAdapterType = ExternalRetrievalAdapterType.HTTP_JSON
    enabled: bool = False
    auth: ExternalRetrievalAuthConfig = Field(default_factory=ExternalRetrievalAuthConfig)
    auth_changed: bool = True
    config: ExternalRetrievalConfig
    timeout_ms: int = 3000
    max_results: int = 10
    source_weight: float = 0.6
    min_confidence: float | None = None
    call_strategy: ExternalRetrievalCallStrategy = (
        ExternalRetrievalCallStrategy.ORIGINAL_QUERY_ONCE
    )
    document_set_ids: list[int] = Field(default_factory=list)


class ExternalRetrievalSourcePatchRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    adapter_type: ExternalRetrievalAdapterType | None = None
    enabled: bool | None = None
    auth: ExternalRetrievalAuthConfig | None = None
    auth_changed: bool = False
    config: ExternalRetrievalConfig | None = None
    timeout_ms: int | None = None
    max_results: int | None = None
    source_weight: float | None = None
    min_confidence: float | None = None
    call_strategy: ExternalRetrievalCallStrategy | None = None
    document_set_ids: list[int] | None = None


class ExternalRetrievalSourceView(BaseModel):
    id: int
    name: str
    description: str | None
    adapter_type: ExternalRetrievalAdapterType
    enabled: bool
    auth: ExternalRetrievalAuthConfig
    config: ExternalRetrievalConfig
    timeout_ms: int
    max_results: int
    source_weight: float
    min_confidence: float | None
    call_strategy: ExternalRetrievalCallStrategy
    document_sets: list[ExternalRetrievalDocumentSetView]
    time_created: datetime | None
    time_updated: datetime | None


class ExternalRetrievalSourceSummary(BaseModel):
    id: int
    name: str
    description: str | None
    adapter_type: ExternalRetrievalAdapterType
    enabled: bool
    endpoint: str
    timeout_ms: int
    max_results: int
    source_weight: float
    min_confidence: float | None
    call_strategy: ExternalRetrievalCallStrategy
    document_sets: list[ExternalRetrievalDocumentSetView]
    time_updated: datetime | None


class ExternalRetrievalAdapterSchema(BaseModel):
    adapter_types: list[str]
    auth_types: list[str]
    request_modes: list[str]
    call_strategies: list[str]
    default_field_mapping: dict[str, list[str]]


class ExternalRetrievalTestConfigRequest(ExternalRetrievalSourceUpsertRequest):
    test: ExternalRetrievalTestRequest


class ExternalRetrievalSourceStatus(BaseModel):
    id: int
    enabled: bool
    status: str
    details: dict[str, Any] = Field(default_factory=dict)

ExternalRetrievalTestResponse = ExternalRetrievalTestResult

