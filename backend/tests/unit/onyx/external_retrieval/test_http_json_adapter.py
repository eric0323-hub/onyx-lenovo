from unittest.mock import Mock
from unittest.mock import patch

import requests

from onyx.external_retrieval.adapters.http_json import HttpJsonExternalRetrievalAdapter
from onyx.external_retrieval.models import ExternalRetrievalConfig
from onyx.external_retrieval.models import ExternalRetrievalSourceConfig
from onyx.external_retrieval.models import ExternalRetrievalTestRequest


def _source_config(*, allow_localhost: bool = True) -> ExternalRetrievalSourceConfig:
    return ExternalRetrievalSourceConfig(
        id=12,
        name="Ontology",
        config=ExternalRetrievalConfig(
            endpoint="http://127.0.0.1:8000/api/retrieval/search",
            allow_localhost=allow_localhost,
        ),
    )


@patch("onyx.external_retrieval.adapters.http_json.requests.post")
def test_http_json_adapter_normalizes_response(mock_post: Mock) -> None:
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "results": [
            {
                "title": "Ontology evidence",
                "content": "Evidence text",
                "confidence": 0.8,
            }
        ]
    }
    mock_post.return_value = response

    result = HttpJsonExternalRetrievalAdapter().test(
        ExternalRetrievalTestRequest(query="battery", limit=3),
        _source_config(),
    )

    assert result.success is True
    assert result.normalized_results[0].title == "Ontology evidence"
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["json"] == {"query": "battery", "limit": 3}
    assert mock_post.call_args.kwargs["allow_redirects"] is False


@patch("onyx.external_retrieval.adapters.http_json.requests.post")
def test_http_json_adapter_timeout_is_fail_result(mock_post: Mock) -> None:
    mock_post.side_effect = requests.Timeout()

    result = HttpJsonExternalRetrievalAdapter().test(
        ExternalRetrievalTestRequest(query="battery", limit=3),
        _source_config(),
    )

    assert result.success is False
    assert result.error_code == "timeout"


def test_http_json_adapter_blocks_localhost_by_default() -> None:
    result = HttpJsonExternalRetrievalAdapter().test(
        ExternalRetrievalTestRequest(query="battery", limit=3),
        _source_config(allow_localhost=False),
    )

    assert result.success is False
    assert result.error_code == "configuration_error"

