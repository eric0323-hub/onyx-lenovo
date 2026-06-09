from __future__ import annotations

import ipaddress
import socket
import time
from typing import Any
from urllib.parse import urlparse

import requests

from onyx.external_retrieval.dedupe import dedupe_external_retrieval_results
from onyx.external_retrieval.errors import ExternalRetrievalConfigurationError
from onyx.external_retrieval.errors import ExternalRetrievalRequestError
from onyx.external_retrieval.errors import ExternalRetrievalResponseError
from onyx.external_retrieval.models import ExternalRetrievalAuthType
from onyx.external_retrieval.models import ExternalRetrievalRequest
from onyx.external_retrieval.models import ExternalRetrievalRequestMode
from onyx.external_retrieval.models import ExternalRetrievalSourceConfig
from onyx.external_retrieval.models import ExternalRetrievalTestRequest
from onyx.external_retrieval.models import ExternalRetrievalTestResult
from onyx.external_retrieval.models import NormalizedExternalRetrievalResult
from onyx.external_retrieval.normalization import normalize_external_retrieval_response
from onyx.utils.logger import setup_logger

logger = setup_logger()

BLOCKED_HEADER_NAMES = {
    "authorization",
    "cookie",
    "host",
    "x-forwarded-for",
    "x-real-ip",
    "x-onyx-tenant",
}


class HttpJsonExternalRetrievalAdapter:
    def validate_config(self, config: ExternalRetrievalSourceConfig) -> None:
        endpoint = config.config.endpoint
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ExternalRetrievalConfigurationError(
                "Endpoint must be an absolute http(s) URL."
            )
        if not config.config.allow_localhost:
            _validate_public_host(parsed.hostname)

        for header_name in config.config.headers:
            if header_name.lower() in BLOCKED_HEADER_NAMES:
                raise ExternalRetrievalConfigurationError(
                    f"Header '{header_name}' cannot be configured directly."
                )

        auth = config.auth
        if auth.type == ExternalRetrievalAuthType.BEARER and not auth.token:
            raise ExternalRetrievalConfigurationError("Bearer token is required.")
        if auth.type == ExternalRetrievalAuthType.API_KEY_HEADER:
            if not auth.api_key_header or not auth.api_key:
                raise ExternalRetrievalConfigurationError(
                    "API key header name and value are required."
                )
        if auth.type == ExternalRetrievalAuthType.BASIC:
            if not auth.username or not auth.password:
                raise ExternalRetrievalConfigurationError(
                    "Basic auth username and password are required."
                )

    def search(
        self,
        request: ExternalRetrievalRequest,
        config: ExternalRetrievalSourceConfig,
    ) -> list[NormalizedExternalRetrievalResult]:
        test_result = self._execute(
            request=request,
            config=config,
            include_raw_response=False,
        )
        if not test_result.success:
            raise ExternalRetrievalRequestError(
                test_result.message or "Search failed.",
                error_code=test_result.error_code,
            )
        return test_result.normalized_results

    def test(
        self,
        request: ExternalRetrievalTestRequest,
        config: ExternalRetrievalSourceConfig,
    ) -> ExternalRetrievalTestResult:
        retrieval_request = ExternalRetrievalRequest(
            query=request.query,
            limit=request.limit,
        )
        return self._execute(
            request=retrieval_request,
            config=config,
            include_raw_response=request.include_raw_response,
        )

    def _execute(
        self,
        request: ExternalRetrievalRequest,
        config: ExternalRetrievalSourceConfig,
        include_raw_response: bool,
    ) -> ExternalRetrievalTestResult:
        try:
            self.validate_config(config)
        except ExternalRetrievalConfigurationError as e:
            return ExternalRetrievalTestResult(
                success=False,
                error_code=e.error_code,
                message=str(e),
            )

        payload = _build_payload(request, config)
        headers = _build_headers(config)
        auth = _build_auth(config)

        start = time.monotonic()
        try:
            response = requests.post(
                config.config.endpoint,
                json=payload,
                headers=headers,
                auth=auth,
                timeout=config.timeout_ms / 1000,
                allow_redirects=False,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
        except requests.Timeout:
            return ExternalRetrievalTestResult(
                success=False,
                latency_ms=int((time.monotonic() - start) * 1000),
                error_code="timeout",
                message=f"External retrieval source timed out after {config.timeout_ms}ms.",
            )
        except requests.RequestException as e:
            return ExternalRetrievalTestResult(
                success=False,
                latency_ms=int((time.monotonic() - start) * 1000),
                error_code="request_error",
                message=str(e),
            )

        if response.status_code < 200 or response.status_code >= 300:
            return ExternalRetrievalTestResult(
                success=False,
                latency_ms=latency_ms,
                error_code="http_error",
                message=f"External source returned HTTP {response.status_code}.",
            )

        try:
            raw_response = response.json()
        except ValueError:
            return ExternalRetrievalTestResult(
                success=False,
                latency_ms=latency_ms,
                error_code="invalid_json",
                message="External source returned non-JSON response.",
            )

        try:
            normalized, invalid, warnings = normalize_external_retrieval_response(
                raw_response,
                config,
            )
            normalized = dedupe_external_retrieval_results(normalized)[
                : config.max_results
            ]
        except ExternalRetrievalResponseError as e:
            return ExternalRetrievalTestResult(
                success=False,
                latency_ms=latency_ms,
                invalid_results=[],
                raw_response=raw_response if include_raw_response else None,
                error_code=e.error_code,
                message=str(e),
            )

        return ExternalRetrievalTestResult(
            success=True,
            latency_ms=latency_ms,
            normalized_results=normalized,
            invalid_results=invalid,
            warnings=warnings,
            raw_response=raw_response if include_raw_response else None,
        )


def _validate_public_host(hostname: str | None) -> None:
    if not hostname:
        raise ExternalRetrievalConfigurationError("Endpoint host is required.")
    try:
        ip = ipaddress.ip_address(hostname)
        _validate_public_ip(ip)
        return
    except ValueError:
        pass

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise ExternalRetrievalConfigurationError(
            f"Could not resolve endpoint host '{hostname}'."
        ) from e

    for addr_info in addr_infos:
        ip = ipaddress.ip_address(addr_info[4][0])
        _validate_public_ip(ip)


def _validate_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ExternalRetrievalConfigurationError(
            "Endpoint resolves to a private or local address. Enable allow_localhost "
            "only for trusted internal test sources."
        )


def _build_payload(
    request: ExternalRetrievalRequest,
    config: ExternalRetrievalSourceConfig,
) -> dict[str, Any]:
    if config.config.request_mode == ExternalRetrievalRequestMode.SIMPLE:
        return {"query": request.query, "limit": request.limit}

    if config.config.request_mode == ExternalRetrievalRequestMode.STANDARD:
        return {
            "schema_version": "1.0",
            "query": request.query,
            "limit": request.limit,
            "filters": {
                "document_sets": request.document_set_names or [],
                "source_types": ["external_retrieval"],
            },
            "options": {},
            "context": {
                "tenant_id": request.tenant_id,
                "user_id": str(request.user_id) if request.user_id else None,
                "request_id": request.request_id,
            },
        }

    if config.config.request_template is None:
        raise ExternalRetrievalRequestError(
            "request_template is required for custom_template mode."
        )
    return _render_template(config.config.request_template, request)


def _render_template(value: Any, request: ExternalRetrievalRequest) -> Any:
    if isinstance(value, str):
        return (
            value.replace("{{query}}", request.query)
            .replace("{{limit}}", str(request.limit))
            .replace("{{user_id}}", str(request.user_id) if request.user_id else "")
            .replace("{{tenant_id}}", request.tenant_id or "")
            .replace("{{request_id}}", request.request_id or "")
        )
    if isinstance(value, dict):
        return {key: _render_template(val, request) for key, val in value.items()}
    if isinstance(value, list):
        return [_render_template(item, request) for item in value]
    return value


def _build_headers(config: ExternalRetrievalSourceConfig) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **config.config.headers,
    }
    auth = config.auth
    if auth.type == ExternalRetrievalAuthType.BEARER and auth.token:
        headers["Authorization"] = f"Bearer {auth.token}"
    elif auth.type == ExternalRetrievalAuthType.API_KEY_HEADER:
        if auth.api_key_header and auth.api_key:
            headers[auth.api_key_header] = auth.api_key
    return headers


def _build_auth(
    config: ExternalRetrievalSourceConfig,
) -> tuple[str, str] | None:
    auth = config.auth
    if auth.type != ExternalRetrievalAuthType.BASIC:
        return None
    if not auth.username or not auth.password:
        return None
    return (auth.username, auth.password)
