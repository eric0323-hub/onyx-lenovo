from __future__ import annotations

from typing import Protocol

from onyx.external_retrieval.models import ExternalRetrievalRequest
from onyx.external_retrieval.models import ExternalRetrievalSourceConfig
from onyx.external_retrieval.models import ExternalRetrievalTestRequest
from onyx.external_retrieval.models import ExternalRetrievalTestResult
from onyx.external_retrieval.models import NormalizedExternalRetrievalResult


class ExternalRetrievalAdapter(Protocol):
    def validate_config(self, config: ExternalRetrievalSourceConfig) -> None:
        ...

    def search(
        self,
        request: ExternalRetrievalRequest,
        config: ExternalRetrievalSourceConfig,
    ) -> list[NormalizedExternalRetrievalResult]:
        ...

    def test(
        self,
        request: ExternalRetrievalTestRequest,
        config: ExternalRetrievalSourceConfig,
    ) -> ExternalRetrievalTestResult:
        ...

