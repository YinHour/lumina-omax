"""Shared SSE streaming helpers for chat/source-chat/ask routers.

Provides three orthogonal concerns:

1. **Heartbeat events** — opt-in heartbeat SSE chunks so the front-end can
   show "still working" while the model takes time to respond. Two regimes:
     - ``heartbeat_until_first_item=True`` (chat-style): heartbeats fire on a
       fixed interval until the first data item is yielded, then stop. After
       that the stream of model tokens is its own keep-alive.
     - ``heartbeat_until_first_item=False`` (ask-style): heartbeats fire when
       a configurable silence threshold is exceeded *since the last item* and
       keep monitoring throughout the entire stream. Suitable for multi-phase
       pipelines where there can be quiet stretches between phases.

2. **Whole-stream timeout** — wraps the producer coroutine in
   ``asyncio.wait_for(..., timeout_seconds)``. On timeout the producer is
   cancelled and ``asyncio.TimeoutError`` is re-raised to the caller, which
   can emit its own ``llm_timeout`` SSE event.

3. **Stable error codes** — :func:`error_code_from_exception` maps the typed
   exceptions in :mod:`open_notebook.exceptions` to short wire identifiers so
   the front-end can dispatch to localized error bubble templates.

The helpers are deliberately framework-agnostic: the producer just pushes SSE
strings onto an :class:`asyncio.Queue`; the helper interleaves heartbeats and
yields everything in order.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional

from loguru import logger

# ---------------------------------------------------------------------------
# Env-var helpers
# ---------------------------------------------------------------------------


def env_positive_float(name: str, default: float) -> float:
    """Read a positive float env var with safe fallback to ``default``."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning(f"Invalid {name}={raw!r}; using default {default}")
        return default
    return value if value > 0 else default


# ---------------------------------------------------------------------------
# SSE event helpers
# ---------------------------------------------------------------------------


def heartbeat_sse_event(stage: str, elapsed_ms_value: int) -> str:
    """Build a ``heartbeat`` SSE event string.

    Clients use ``stage`` as the i18n key and ``elapsed_ms`` to show how long
    the request has been running.
    """
    event = {
        "type": "heartbeat",
        "stage": stage,
        "elapsed_ms": elapsed_ms_value,
    }
    return f"data: {json.dumps(event)}\n\n"


def llm_timeout_sse_event(timeout_seconds: float) -> str:
    """Build a structured ``llm_timeout`` SSE error event."""
    event = {
        "type": "error",
        "error_code": "llm_timeout",
        "timeout_seconds": timeout_seconds,
        "message": (
            f"Model response timed out after {int(timeout_seconds)}s. "
            "Try shrinking the included sources or notes and ask again."
        ),
    }
    return f"data: {json.dumps(event)}\n\n"


def error_sse_event(
    error_code: str,
    message: str,
    **extra: Any,
) -> str:
    """Build an ``error`` SSE event with a stable ``error_code`` identifier."""
    event: dict[str, Any] = {
        "type": "error",
        "error_code": error_code,
        "message": message,
    }
    event.update(extra)
    return f"data: {json.dumps(event)}\n\n"


def reasoning_status_sse_event() -> str:
    """Signal that the model is reasoning without exposing chain-of-thought."""
    event = {
        "type": "reasoning_status",
        "status": "active",
    }
    return f"data: {json.dumps(event)}\n\n"


def extract_reasoning_content(chunk: Any) -> str:
    """Read provider-specific reasoning fields without logging their contents."""
    if isinstance(chunk, dict):
        reasoning = chunk.get("reasoning_content")
        if reasoning:
            return str(reasoning)
        additional_kwargs = chunk.get("additional_kwargs")
        if isinstance(additional_kwargs, dict):
            reasoning = additional_kwargs.get("reasoning_content")
            if reasoning:
                return str(reasoning)

    for attribute in ("additional_kwargs", "response_metadata"):
        metadata = getattr(chunk, attribute, None)
        if isinstance(metadata, dict):
            reasoning = metadata.get("reasoning_content")
            if reasoning:
                return str(reasoning)

    return ""


_THINK_BLOCK = re.compile(r"<think\b[^>]*>[\s\S]*?</think\s*>", re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think\b[^>]*>", re.IGNORECASE)
_THINK_OPEN_PREFIX = re.compile(r"<think\b[^>]*\Z", re.IGNORECASE)
_THINK_CLOSE = re.compile(r"</think\s*>", re.IGNORECASE)
_THINK_TAG_PREFIXES = ("<think", "</think")


def _visible_stream_content(content: str) -> str:
    visible = _THINK_BLOCK.sub("", content)
    open_match = _THINK_OPEN.search(visible)
    close_match = _THINK_CLOSE.search(visible)

    if close_match and (not open_match or close_match.start() < open_match.start()):
        visible = visible[close_match.end() :]

    remaining_open = _THINK_OPEN.search(visible)
    if remaining_open:
        visible = visible[: remaining_open.start()]
    else:
        incomplete_open = _THINK_OPEN_PREFIX.search(visible)
        if incomplete_open:
            visible = visible[: incomplete_open.start()]

    lower_visible = visible.lower()
    max_tag_prefix_length = max(len(prefix) for prefix in _THINK_TAG_PREFIXES)
    for length in range(min(len(visible), max_tag_prefix_length), 0, -1):
        suffix = lower_visible[-length:]
        if any(prefix.startswith(suffix) for prefix in _THINK_TAG_PREFIXES):
            return visible[:-length]

    return visible


class SafeModelContentStream:
    """Separate public answer deltas from inline model reasoning blocks."""

    def __init__(self) -> None:
        self._raw_content = ""
        self._visible_content = ""
        self._reasoning_seen = False

    def observe_reasoning(self) -> bool:
        """Return ``True`` only when reasoning is observed for the first time."""
        if self._reasoning_seen:
            return False
        self._reasoning_seen = True
        return True

    def feed(self, content: str) -> tuple[str, bool]:
        if not content:
            return "", False

        self._raw_content += content
        reasoning_detected = bool(
            _THINK_OPEN.search(self._raw_content)
            or _THINK_CLOSE.search(self._raw_content)
        )
        first_reasoning = reasoning_detected and self.observe_reasoning()
        visible = _visible_stream_content(self._raw_content)

        if not visible.startswith(self._visible_content):
            # A malformed provider stream reclassified previously emitted text
            # as reasoning. Never emit more raw text from that sequence.
            return "", first_reasoning

        delta = visible[len(self._visible_content) :]
        self._visible_content = visible
        return delta, first_reasoning

    def canonical_visible(self, content: str) -> str:
        """Return the safe visible value from a complete provider response."""
        return _visible_stream_content(content)


# ---------------------------------------------------------------------------
# Error code mapping
# ---------------------------------------------------------------------------


# Stable wire identifiers surfaced to the front-end. Keep this dict additive —
# clients ignore unknown codes and fall back to a generic bubble carrying the
# server-provided ``message``. The front-end mirror lives in
# ``frontend/src/lib/constants/chat-error-codes.ts``.
ERROR_CODE_BY_EXCEPTION_NAME: dict[str, str] = {
    "AuthenticationError": "authentication",
    "RateLimitError": "rate_limit",
    "ConfigurationError": "configuration",
    "NetworkError": "network",
    "ExternalServiceError": "external_service",
    "InvalidInputError": "invalid_input",
    "NotFoundError": "not_found",
    "OpenNotebookError": "internal_error",
}


def error_code_from_exception(exc_class: type) -> str:
    """Map a typed exception class name to a stable wire ``error_code``."""
    return ERROR_CODE_BY_EXCEPTION_NAME.get(exc_class.__name__, "internal_error")


# ---------------------------------------------------------------------------
# Streaming helper
# ---------------------------------------------------------------------------


_PRODUCER_DONE_SENTINEL: object = object()


async def stream_with_heartbeat_and_timeout(
    *,
    run_producer: Callable[[asyncio.Queue], Awaitable[None]],
    timeout_seconds: float,
    heartbeat_seconds: float,
    started_at: float,
    heartbeat_stage: str = "awaiting_model",
    heartbeat_until_first_item: bool = True,
    on_heartbeat_sent: Optional[Callable[[int], None]] = None,
) -> AsyncGenerator[str, None]:
    """Run ``run_producer(queue)`` and yield each SSE string it pushes,
    interleaved with heartbeats. Enforces a whole-stream timeout.

    :param run_producer: Coroutine factory; receives the output ``asyncio.Queue``
        and must push SSE strings into it. Returning normally ends the stream.
    :param timeout_seconds: Maximum wall-clock seconds the producer can run.
        On timeout the producer is cancelled and ``asyncio.TimeoutError`` is
        re-raised to the caller.
    :param heartbeat_seconds: Heartbeat cadence in seconds.
    :param started_at: ``time.perf_counter()`` snapshot at request entry; used
        to compute the ``elapsed_ms`` field in heartbeat events.
    :param heartbeat_stage: Value of the ``stage`` field on each heartbeat.
    :param heartbeat_until_first_item: ``True`` stops heartbeats after the
        first yielded item (chat semantics). ``False`` keeps monitoring for
        silence throughout (ask semantics).
    :param on_heartbeat_sent: Optional callback invoked with the running
        heartbeat count whenever a heartbeat is sent. Lets the caller log
        ``heartbeats_sent`` in its own observability traces.
    """
    out_queue: asyncio.Queue[Optional[Any]] = asyncio.Queue()
    state = {
        "first_item_seen": False,
        "last_item_at": started_at,
        "heartbeats_sent": 0,
    }

    async def heartbeat_loop() -> None:
        try:
            if heartbeat_until_first_item:
                # Chat-style: emit one heartbeat per cadence until the first
                # real item arrives, then stop.
                while not state["first_item_seen"]:
                    await asyncio.sleep(heartbeat_seconds)
                    if state["first_item_seen"]:
                        return
                    state["heartbeats_sent"] += 1
                    if on_heartbeat_sent is not None:
                        try:
                            on_heartbeat_sent(state["heartbeats_sent"])
                        except Exception:
                            pass
                    await out_queue.put(
                        heartbeat_sse_event(
                            heartbeat_stage,
                            int((time.perf_counter() - started_at) * 1000),
                        )
                    )
            else:
                # Ask-style: emit a heartbeat any time we go ``heartbeat_seconds``
                # without a single item from the producer, throughout the run.
                while True:
                    await asyncio.sleep(heartbeat_seconds)
                    silence = time.perf_counter() - state["last_item_at"]
                    if silence + 0.05 < heartbeat_seconds:  # 50ms slack
                        continue
                    state["heartbeats_sent"] += 1
                    if on_heartbeat_sent is not None:
                        try:
                            on_heartbeat_sent(state["heartbeats_sent"])
                        except Exception:
                            pass
                    await out_queue.put(
                        heartbeat_sse_event(
                            heartbeat_stage,
                            int((time.perf_counter() - started_at) * 1000),
                        )
                    )
        except asyncio.CancelledError:
            return

    producer_task = asyncio.create_task(run_producer(out_queue))
    heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def finalize_producer() -> None:
        try:
            await asyncio.wait_for(producer_task, timeout=timeout_seconds)
        finally:
            await out_queue.put(_PRODUCER_DONE_SENTINEL)

    finalize_task = asyncio.create_task(finalize_producer())

    try:
        while True:
            item = await out_queue.get()
            if item is _PRODUCER_DONE_SENTINEL:
                break
            assert isinstance(item, str)
            state["first_item_seen"] = True
            state["last_item_at"] = time.perf_counter()
            yield item
            await asyncio.sleep(0.001)
    finally:
        heartbeat_task.cancel()
        if not producer_task.done():
            producer_task.cancel()
        for task in (heartbeat_task, producer_task, finalize_task):
            try:
                await task
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception:
                pass

    if finalize_task.done():
        exc = finalize_task.exception()
        if exc is not None:
            raise exc
