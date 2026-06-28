"""Tests for the shared SSE streaming helpers (api/sse_helpers.py).

Covers the wire contracts that §32 promises to source chat and ask:

- ``heartbeat_sse_event`` / ``llm_timeout_sse_event`` / ``error_sse_event``
  produce the SSE strings that the front-end parses.
- ``error_code_from_exception`` maps typed exceptions to stable wire codes.
- ``stream_with_heartbeat_and_timeout`` interleaves heartbeats with producer
  output and enforces the overall timeout, in both ``until_first_item`` and
  silence-based modes.
"""

import asyncio
import json
import time

import pytest


def test_heartbeat_sse_event_shape():
    from api.sse_helpers import heartbeat_sse_event

    raw = heartbeat_sse_event("awaiting_model", 12345)
    assert raw.startswith("data: ")
    payload = json.loads(raw.removeprefix("data: ").strip())
    assert payload == {
        "type": "heartbeat",
        "stage": "awaiting_model",
        "elapsed_ms": 12345,
    }


def test_llm_timeout_sse_event_includes_seconds():
    from api.sse_helpers import llm_timeout_sse_event

    raw = llm_timeout_sse_event(240.0)
    payload = json.loads(raw.removeprefix("data: ").strip())
    assert payload["type"] == "error"
    assert payload["error_code"] == "llm_timeout"
    assert payload["timeout_seconds"] == 240.0
    assert "timed out" in payload["message"].lower()


def test_error_sse_event_passes_through_extra_fields():
    from api.sse_helpers import error_sse_event

    raw = error_sse_event("rate_limit", "Try again later.", retry_after=30)
    payload = json.loads(raw.removeprefix("data: ").strip())
    assert payload == {
        "type": "error",
        "error_code": "rate_limit",
        "message": "Try again later.",
        "retry_after": 30,
    }


def test_error_code_from_exception_covers_known_classes():
    from api.sse_helpers import error_code_from_exception
    from open_notebook.exceptions import (
        AuthenticationError,
        ConfigurationError,
        ExternalServiceError,
        InvalidInputError,
        NetworkError,
        NotFoundError,
        OpenNotebookError,
        RateLimitError,
    )

    assert error_code_from_exception(AuthenticationError) == "authentication"
    assert error_code_from_exception(RateLimitError) == "rate_limit"
    assert error_code_from_exception(ConfigurationError) == "configuration"
    assert error_code_from_exception(NetworkError) == "network"
    assert error_code_from_exception(ExternalServiceError) == "external_service"
    assert error_code_from_exception(InvalidInputError) == "invalid_input"
    assert error_code_from_exception(NotFoundError) == "not_found"
    assert error_code_from_exception(OpenNotebookError) == "internal_error"


def test_error_code_from_exception_unknown_falls_back():
    from api.sse_helpers import error_code_from_exception

    class _Weird(Exception):
        pass

    assert error_code_from_exception(_Weird) == "internal_error"
    assert error_code_from_exception(Exception) == "internal_error"


def test_env_positive_float_safe_fallback(monkeypatch):
    from api.sse_helpers import env_positive_float

    monkeypatch.setenv("__SSE_TEST_FLOAT__", "12.5")
    assert env_positive_float("__SSE_TEST_FLOAT__", 5.0) == 12.5
    monkeypatch.setenv("__SSE_TEST_FLOAT__", "abc")
    assert env_positive_float("__SSE_TEST_FLOAT__", 5.0) == 5.0
    monkeypatch.setenv("__SSE_TEST_FLOAT__", "0")
    assert env_positive_float("__SSE_TEST_FLOAT__", 5.0) == 5.0
    monkeypatch.delenv("__SSE_TEST_FLOAT__", raising=False)
    assert env_positive_float("__SSE_TEST_FLOAT__", 5.0) == 5.0


@pytest.mark.asyncio
async def test_stream_with_heartbeat_until_first_item_emits_heartbeats_then_stops():
    """Chat-style heartbeat: fires until the first producer item, then quiet."""
    from api.sse_helpers import stream_with_heartbeat_and_timeout

    async def producer(queue: asyncio.Queue) -> None:
        # Sleep enough to allow 2-3 heartbeats at 0.05s cadence.
        await asyncio.sleep(0.20)
        await queue.put('data: {"type":"ai_message","content":"hi"}\n\n')
        await asyncio.sleep(0.30)  # silence after first item
        await queue.put('data: {"type":"complete"}\n\n')

    events: list[dict] = []
    async for raw in stream_with_heartbeat_and_timeout(
        run_producer=producer,
        timeout_seconds=5.0,
        heartbeat_seconds=0.05,
        started_at=time.perf_counter(),
        heartbeat_until_first_item=True,
    ):
        events.append(json.loads(raw.removeprefix("data: ").strip()))

    types = [e["type"] for e in events]
    # At least one heartbeat must arrive before the first ai_message.
    first_ai = types.index("ai_message")
    first_hb = types.index("heartbeat")
    assert first_hb < first_ai
    # After the first ai_message, no more heartbeats should fire even though we
    # paused 0.3s; heartbeat_until_first_item=True turns the loop off.
    post_first_ai = types[first_ai + 1:]
    assert "heartbeat" not in post_first_ai
    assert "complete" in post_first_ai


@pytest.mark.asyncio
async def test_stream_with_heartbeat_silence_based_fires_during_quiet_phases():
    """Ask-style heartbeat: fires on silence, even after items have arrived."""
    from api.sse_helpers import stream_with_heartbeat_and_timeout

    async def producer(queue: asyncio.Queue) -> None:
        await queue.put('data: {"type":"strategy"}\n\n')
        # Long pause between strategy and first answer.
        await asyncio.sleep(0.25)
        await queue.put('data: {"type":"answer"}\n\n')
        await queue.put('data: {"type":"final_answer"}\n\n')

    events: list[dict] = []
    async for raw in stream_with_heartbeat_and_timeout(
        run_producer=producer,
        timeout_seconds=5.0,
        heartbeat_seconds=0.05,
        started_at=time.perf_counter(),
        heartbeat_until_first_item=False,
    ):
        events.append(json.loads(raw.removeprefix("data: ").strip()))

    types = [e["type"] for e in events]
    assert "strategy" in types
    # Heartbeats must appear between strategy and answer (during silence).
    strat_idx = types.index("strategy")
    ans_idx = types.index("answer")
    between = types[strat_idx + 1:ans_idx]
    assert "heartbeat" in between, f"expected heartbeat between strategy and answer in {types}"


@pytest.mark.asyncio
async def test_stream_with_heartbeat_enforces_timeout():
    from api.sse_helpers import stream_with_heartbeat_and_timeout

    async def hanging_producer(queue: asyncio.Queue) -> None:
        await asyncio.sleep(2.0)  # never yields anything

    async def consume():
        async for _ in stream_with_heartbeat_and_timeout(
            run_producer=hanging_producer,
            timeout_seconds=0.15,
            heartbeat_seconds=0.05,
            started_at=time.perf_counter(),
            heartbeat_until_first_item=True,
        ):
            pass

    with pytest.raises(asyncio.TimeoutError):
        await consume()


@pytest.mark.asyncio
async def test_stream_with_heartbeat_propagates_producer_exception():
    from api.sse_helpers import stream_with_heartbeat_and_timeout
    from open_notebook.exceptions import RateLimitError

    async def failing_producer(queue: asyncio.Queue) -> None:
        await asyncio.sleep(0.05)
        raise RateLimitError("upstream limited")

    async def consume():
        async for _ in stream_with_heartbeat_and_timeout(
            run_producer=failing_producer,
            timeout_seconds=5.0,
            heartbeat_seconds=0.05,
            started_at=time.perf_counter(),
        ):
            pass

    with pytest.raises(RateLimitError):
        await consume()


@pytest.mark.asyncio
async def test_stream_with_heartbeat_on_heartbeat_sent_callback():
    """The optional ``on_heartbeat_sent`` callback exposes the running count
    so callers can log ``heartbeats_sent`` in their own observability traces.
    """
    from api.sse_helpers import stream_with_heartbeat_and_timeout

    counts: list[int] = []

    async def slow_producer(queue: asyncio.Queue) -> None:
        await asyncio.sleep(0.20)
        await queue.put('data: {"type":"ai_message"}\n\n')

    async for _ in stream_with_heartbeat_and_timeout(
        run_producer=slow_producer,
        timeout_seconds=5.0,
        heartbeat_seconds=0.05,
        started_at=time.perf_counter(),
        on_heartbeat_sent=counts.append,
    ):
        pass

    assert counts, f"expected at least one heartbeat callback in {counts}"
    # Counter is monotonically increasing (1, 2, 3, ...).
    for prev, curr in zip(counts, counts[1:]):
        assert curr == prev + 1
