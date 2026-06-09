from __future__ import annotations

from onyx.external_retrieval.adapters.base import ExternalRetrievalAdapter
from onyx.external_retrieval.adapters.http_json import HttpJsonExternalRetrievalAdapter
from onyx.external_retrieval.adapters.ontology import OntologyExternalRetrievalAdapter
from onyx.external_retrieval.models import ExternalRetrievalAdapterType


def get_external_retrieval_adapter(
    adapter_type: ExternalRetrievalAdapterType,
) -> ExternalRetrievalAdapter:
    if adapter_type == ExternalRetrievalAdapterType.HTTP_JSON:
        return HttpJsonExternalRetrievalAdapter()
    if adapter_type == ExternalRetrievalAdapterType.ONTOLOGY:
        return OntologyExternalRetrievalAdapter()
    raise ValueError(f"Unsupported external retrieval adapter type: {adapter_type}")

