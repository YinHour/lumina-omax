from __future__ import annotations

import asyncio
import email.utils
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from open_notebook.scientific_connectors.models import ScientificConnectorError

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_RESPONSE_BYTES = 4_000_000
RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def _positive_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After") if response else None
    if retry_after:
        try:
            return min(30.0, max(0.0, float(retry_after)))
        except ValueError:
            try:
                parsed = email.utils.parsedate_to_datetime(retry_after)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return min(
                    30.0,
                    max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds()),
                )
            except (TypeError, ValueError):
                pass
    return min(8.0, 0.5 * (2**attempt))


async def request(
    url: str,
    *,
    database: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    response_format: str = "json",
    transport: httpx.AsyncBaseTransport | None = None,
) -> Any:
    timeout = _positive_float(
        "SCIENTIFIC_DATABASE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS
    )
    max_attempts = _positive_int(
        "SCIENTIFIC_DATABASE_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS
    )
    max_bytes = _positive_int(
        "SCIENTIFIC_DATABASE_MAX_RESPONSE_BYTES", DEFAULT_MAX_RESPONSE_BYTES
    )
    request_headers = {
        "Accept": "application/json"
        if response_format == "json"
        else "application/atom+xml",
        "User-Agent": "Lumiton-Omax/2 scientific-database-connector",
        **(headers or {}),
    }

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        transport=transport,
    ) as client:
        for attempt in range(max_attempts):
            response: httpx.Response | None = None
            try:
                response = await client.get(url, params=params, headers=request_headers)
                if (
                    response.status_code in RETRYABLE_STATUSES
                    and attempt + 1 < max_attempts
                ):
                    await asyncio.sleep(_retry_delay(response, attempt))
                    continue
                response.raise_for_status()
                content_length = response.headers.get("Content-Length")
                try:
                    declared_bytes = int(content_length) if content_length else None
                except ValueError:
                    declared_bytes = None
                if declared_bytes is not None and declared_bytes > max_bytes:
                    raise ScientificConnectorError(
                        "response_too_large",
                        f"{database} response exceeded the configured size limit",
                        database=database,
                    )
                if len(response.content) > max_bytes:
                    raise ScientificConnectorError(
                        "response_too_large",
                        f"{database} response exceeded the configured size limit",
                        database=database,
                    )
                if response_format == "text":
                    return response.text
                try:
                    return response.json()
                except ValueError as exc:
                    raise ScientificConnectorError(
                        "invalid_response",
                        f"{database} returned an invalid JSON response",
                        database=database,
                    ) from exc
            except ScientificConnectorError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt + 1 < max_attempts:
                    await asyncio.sleep(_retry_delay(response, attempt))
                    continue
                raise ScientificConnectorError(
                    "upstream_unavailable",
                    f"{database} did not respond before the request deadline",
                    database=database,
                    retryable=True,
                ) from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                code = "rate_limited" if status == 429 else "upstream_error"
                raise ScientificConnectorError(
                    code,
                    f"{database} returned HTTP {status}",
                    database=database,
                    retryable=status in RETRYABLE_STATUSES,
                ) from exc

    raise ScientificConnectorError(
        "upstream_unavailable",
        f"{database} request failed",
        database=database,
        retryable=True,
    )
