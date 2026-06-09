from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from onyx.external_retrieval.errors import ExternalRetrievalResponseError
from onyx.external_retrieval.models import ExternalRetrievalInvalidResult
from onyx.external_retrieval.models import ExternalRetrievalSourceConfig
from onyx.external_retrieval.models import NormalizedExternalRetrievalResult

RESULT_PATH_FALLBACKS = [
    "$.results",
    "$.data.results",
    "$.articles",
    "$.data.articles",
]

CONTENT_PATH_FALLBACKS = [
    "$.content",
    "$.evidence_text",
    "$.snippet",
    "$.text",
    "$.summary",
    "$.article",
    "$.article.content",
    "$.article.text",
    "$.article.body",
    "$.body",
]

TITLE_PATH_FALLBACKS = [
    "$.title",
    "$.article_title",
    "$.article.title",
    "$.entity.name",
    "$.source.title",
    "$.provenance[0].title",
]

URL_PATH_FALLBACKS = [
    "$.url",
    "$.article_url",
    "$.link",
    "$.source.url",
    "$.provenance[0].url",
]

SOURCE_ID_PATH_FALLBACKS = [
    "$.source_id",
    "$.result_id",
    "$.id",
    "$.article_id",
    "$.source.source_id",
    "$.provenance[0].source_id",
]

SCORE_PATH_FALLBACKS = [
    "$.score",
    "$.relevance_score",
    "$.confidence",
]

CONFIDENCE_PATH_FALLBACKS = [
    "$.confidence",
    "$.trust_score",
    "$.score",
]

UPDATED_AT_PATH_FALLBACKS = [
    "$.updated_at",
    "$.article_updated_at",
    "$.source.updated_at",
    "$.provenance[0].updated_at",
]

CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WHITESPACE_RE = re.compile(r"\s+")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _iter_path_parts(path: str) -> Iterable[str | int]:
    normalized = path.strip()
    if normalized.startswith("$."):
        normalized = normalized[2:]
    elif normalized == "$":
        return []
    elif normalized.startswith("$"):
        normalized = normalized[1:].lstrip(".")

    if not normalized:
        return []

    for part in normalized.split("."):
        remaining = part
        while "[" in remaining:
            before, after = remaining.split("[", 1)
            if before:
                yield before
            index, remaining_after = after.split("]", 1)
            yield int(index)
            remaining = remaining_after.lstrip(".")
        if remaining:
            yield remaining


def _value_at_path(obj: Any, path: str) -> Any:
    current = obj
    for part in _iter_path_parts(path):
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return None
            current = current[part]
            continue

        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None

    return current


def _first_value(obj: Any, paths: list[str]) -> Any:
    for path in paths:
        value = _value_at_path(obj, path)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _stringify_content(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        # Article fields occasionally come back as structured objects. Preserve
        # readable values without leaking a huge JSON blob into the LLM context.
        for key in ("content", "text", "body", "summary", "article"):
            nested = _stringify_content(value.get(key))
            if nested:
                return nested
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list):
        parts = [_stringify_content(item) for item in value]
        return "\n".join(part for part in parts if part)
    return str(value)


def _normalize_content(value: Any, max_chars: int) -> str | None:
    string_value = _stringify_content(value)
    if string_value is None:
        return None
    cleaned = CONTROL_CHAR_RE.sub("", string_value)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    if not cleaned:
        return None
    return cleaned[:max_chars]


def _normalize_text_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
    else:
        text = str(value).strip()
    return text or None


def _normalize_url(value: Any) -> str | None:
    text = _normalize_text_value(value)
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        return text
    if text.startswith("/") or "/" in text:
        # Some internal external sources return repository-relative document
        # paths. Preserve them so citations can still point at source metadata.
        return text
    if not parsed.scheme or not parsed.netloc:
        return None
    return text


def _title_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    candidate = f"{parsed.netloc}{parsed.path}".rstrip("/")
    return candidate or parsed.netloc or None


def _title_from_content(content: str) -> str:
    first_line = content.splitlines()[0].strip()
    return first_line[:120] if first_line else "External result"


def _parse_datetime(value: Any) -> datetime | None:
    text = _normalize_text_value(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_score(
    value: Any,
    *,
    rank: int,
    score_scale: float | None,
) -> float:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            value = None

    if isinstance(value, (int, float)):
        score = float(value)
        if score_scale and score_scale > 0:
            score = score / score_scale
        elif score > 1 and score <= 100:
            score = score / 100
        return min(max(score, 0), 1)

    return 1.0 / (rank + 1)


def _normalize_confidence(
    value: Any,
    *,
    score_scale: float | None,
) -> float | None:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    if not isinstance(value, (int, float)):
        return None
    confidence = float(value)
    if score_scale and score_scale > 0:
        confidence = confidence / score_scale
    elif confidence > 1 and confidence <= 100:
        confidence = confidence / 100
    return min(max(confidence, 0), 1)


def _available_fields(obj: Any, prefix: str = "") -> list[str]:
    if not isinstance(obj, dict):
        return []
    fields: list[str] = []
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        fields.append(path)
        if isinstance(value, dict):
            fields.extend(_available_fields(value, path))
    return fields


def _field_paths(
    source_config: ExternalRetrievalSourceConfig,
    field_name: str,
    fallbacks: list[str],
) -> list[str]:
    configured = source_config.config.field_mapping.get(field_name) or []
    return [*configured, *fallbacks]


def _extract_result_array(
    response_json: Any,
    source_config: ExternalRetrievalSourceConfig,
) -> list[Any]:
    if isinstance(response_json, list):
        return response_json

    if not isinstance(response_json, dict):
        raise ExternalRetrievalResponseError(
            "External response must be a JSON object or array."
        )

    candidate_paths = (
        [source_config.config.result_path] if source_config.config.result_path else []
    ) + RESULT_PATH_FALLBACKS
    for path in candidate_paths:
        if not path:
            continue
        value = _value_at_path(response_json, path)
        if isinstance(value, list):
            return value

    raise ExternalRetrievalResponseError(
        "External response does not contain a result array."
    )


def normalize_external_retrieval_response(
    response_json: Any,
    source_config: ExternalRetrievalSourceConfig,
) -> tuple[
    list[NormalizedExternalRetrievalResult],
    list[ExternalRetrievalInvalidResult],
    list[str],
]:
    results = _extract_result_array(response_json, source_config)
    normalized_results: list[NormalizedExternalRetrievalResult] = []
    invalid_results: list[ExternalRetrievalInvalidResult] = []
    warnings: list[str] = []

    for index, raw_result in enumerate(results):
        content_value = _first_value(
            raw_result,
            _field_paths(source_config, "content", CONTENT_PATH_FALLBACKS),
        )
        content = _normalize_content(
            content_value,
            source_config.config.max_content_chars,
        )
        if content is None:
            invalid_results.append(
                ExternalRetrievalInvalidResult(
                    index=index,
                    reason="No content candidate found.",
                    available_fields=_available_fields(raw_result),
                )
            )
            continue

        url = _normalize_url(
            _first_value(raw_result, _field_paths(source_config, "url", URL_PATH_FALLBACKS))
        )
        title = _normalize_text_value(
            _first_value(
                raw_result,
                _field_paths(source_config, "title", TITLE_PATH_FALLBACKS),
            )
        )
        if title is None:
            title = _title_from_url(url) or _title_from_content(content)
        if not title:
            title = f"External result {index + 1}"

        score_value = _first_value(
            raw_result,
            _field_paths(source_config, "score", SCORE_PATH_FALLBACKS),
        )
        score = _normalize_score(
            score_value,
            rank=index,
            score_scale=source_config.config.score_scale,
        )

        confidence = _normalize_confidence(
            _first_value(
                raw_result,
                _field_paths(
                    source_config,
                    "confidence",
                    CONFIDENCE_PATH_FALLBACKS,
                ),
            ),
            score_scale=source_config.config.score_scale,
        )
        if (
            source_config.min_confidence is not None
            and confidence is not None
            and confidence < source_config.min_confidence
        ):
            invalid_results.append(
                ExternalRetrievalInvalidResult(
                    index=index,
                    reason=(
                        f"Confidence {confidence:.3f} is below configured "
                        f"minimum {source_config.min_confidence:.3f}."
                    ),
                    available_fields=_available_fields(raw_result),
                )
            )
            continue

        source_id = _normalize_text_value(
            _first_value(
                raw_result,
                _field_paths(source_config, "source_id", SOURCE_ID_PATH_FALLBACKS),
            )
        )
        result_id = _normalize_text_value(_value_at_path(raw_result, "$.result_id"))
        canonical_key = _normalize_text_value(
            _value_at_path(raw_result, "$.canonical_key")
        )
        fact_key = _normalize_text_value(_value_at_path(raw_result, "$.fact_key"))
        updated_at = _parse_datetime(
            _first_value(
                raw_result,
                _field_paths(source_config, "updated_at", UPDATED_AT_PATH_FALLBACKS),
            )
        )

        content_fingerprint = _sha256(content)
        dedupe_basis = fact_key or canonical_key or source_id or url or content_fingerprint
        dedupe_key = _sha256(dedupe_basis)
        source_prefix = str(source_config.id or source_config.name)
        document_id = f"external_retrieval:{source_prefix}:{dedupe_key}"

        result_warnings: list[str] = []
        if url is None:
            result_warnings.append("Result has no URL; citation quality will be lower.")
        warnings.extend(result_warnings)

        metadata: dict[str, str | list[str]] = {
            "external_source_name": source_config.name,
            "external_adapter_type": source_config.adapter_type.value,
            "external_content_fingerprint": content_fingerprint,
            "external_dedupe_key": dedupe_key,
        }
        if source_config.id is not None:
            metadata["external_source_id"] = str(source_config.id)
        if source_id:
            metadata["external_result_source_id"] = source_id
        if result_id:
            metadata["external_result_id"] = result_id
        if canonical_key:
            metadata["external_canonical_key"] = canonical_key
        if fact_key:
            metadata["external_fact_key"] = fact_key
        if confidence is not None:
            metadata["external_confidence"] = f"{confidence:.6f}"

        normalized_results.append(
            NormalizedExternalRetrievalResult(
                index=index,
                title=title,
                content=content,
                url=url,
                score=score,
                confidence=confidence,
                source_id=source_id,
                result_id=result_id,
                canonical_key=canonical_key,
                fact_key=fact_key,
                dedupe_key=dedupe_key,
                content_fingerprint=content_fingerprint,
                document_id=document_id,
                updated_at=updated_at,
                metadata=metadata,
                warnings=result_warnings,
            )
        )

    if results and not normalized_results:
        raise ExternalRetrievalResponseError(
            "All external results are missing content after fallback mapping."
        )

    return normalized_results, invalid_results, warnings
