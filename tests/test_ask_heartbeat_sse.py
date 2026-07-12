"""Tests for Ask SSE heartbeat + llm_timeout + error_code wiring (§32)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_stream_ask_response_emits_error_code_for_rate_limit(monkeypatch):
    """Ask should surface an SSE error event with a stable wire ``error_code``
    when the underlying graph raises a typed exception."""
    from api.routers import search as search_mod
    from open_notebook.exceptions import RateLimitError

    monkeypatch.setattr(search_mod, "ASK_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(search_mod, "ASK_LLM_TIMEOUT_SECONDS", 5.0)

    async def _raising_stream(*, input, config=None, version=None):  # noqa: A002
        raise RateLimitError("Rate limit exceeded; please retry later.")
        if False:
            yield {}  # pragma: no cover

    fake_graph = MagicMock()
    fake_graph.astream_events = _raising_stream
    monkeypatch.setattr(search_mod, "ask_graph", fake_graph)

    strategy_model = MagicMock(id="model:strategy")
    answer_model = MagicMock(id="model:answer")
    final_answer_model = MagicMock(id="model:final")

    events: list[dict] = []
    async for raw in search_mod.stream_ask_response(
        question="why is the slurry foaming?",
        strategy_model=strategy_model,
        answer_model=answer_model,
        final_answer_model=final_answer_model,
        corpus_stats={"total_sources": 10, "embedded_sources": 8},
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    # Status/coverage events always fire before the graph producer can fail.
    assert events[0].get("type") == "status"
    assert events[0].get("stage") == "received"
    assert events[1].get("type") == "coverage"
    error_event = next((e for e in events if e.get("type") == "error"), None)
    assert error_event is not None
    assert error_event.get("error_code") == "rate_limit"
    assert "rate limit" in (error_event.get("message") or "").lower()


@pytest.mark.asyncio
async def test_stream_ask_response_emits_llm_timeout(monkeypatch):
    """Ask must emit a structured ``llm_timeout`` SSE event when the graph
    fails to yield any chunk before ``ASK_LLM_TIMEOUT_SECONDS``."""
    from api.routers import search as search_mod

    monkeypatch.setattr(search_mod, "ASK_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(search_mod, "ASK_LLM_TIMEOUT_SECONDS", 0.15)

    async def _hanging_stream(*, input, config=None, version=None):  # noqa: A002
        await asyncio.sleep(2.0)
        if False:
            yield {}  # pragma: no cover

    fake_graph = MagicMock()
    fake_graph.astream_events = _hanging_stream
    monkeypatch.setattr(search_mod, "ask_graph", fake_graph)

    strategy_model = MagicMock(id="model:strategy")
    answer_model = MagicMock(id="model:answer")
    final_answer_model = MagicMock(id="model:final")

    events: list[dict] = []
    async for raw in search_mod.stream_ask_response(
        question="why is the slurry foaming?",
        strategy_model=strategy_model,
        answer_model=answer_model,
        final_answer_model=final_answer_model,
        corpus_stats={"total_sources": 10, "embedded_sources": 8},
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    types = [e.get("type") for e in events]
    assert "complete" not in types
    timeout_event = next((e for e in events if e.get("type") == "error"), None)
    assert timeout_event is not None
    assert timeout_event.get("error_code") == "llm_timeout"
    assert timeout_event.get("timeout_seconds") == 0.15


@pytest.mark.asyncio
async def test_stream_ask_response_emits_silence_heartbeats(monkeypatch):
    """Ask uses silence-based heartbeats: if a phase takes longer than
    ``ASK_STREAM_HEARTBEAT_SECONDS`` to produce something, a heartbeat must
    arrive even after earlier items already came through."""
    from api.routers import search as search_mod

    monkeypatch.setattr(search_mod, "ASK_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(search_mod, "ASK_LLM_TIMEOUT_SECONDS", 5.0)

    async def _slow_stream(*, input, config=None, version=None):  # noqa: A002
        # Pause to force at least one heartbeat after the eagerly-yielded
        # ``coverage`` event but before any producer item.
        await asyncio.sleep(0.25)
        # Yield a single final_answer-ish event so the stream ends cleanly.
        yield {
            "event": "on_chain_end",
            "name": "write_final_answer",
            "data": {"output": {"final_answer": "ok"}},
        }

    fake_graph = MagicMock()
    fake_graph.astream_events = _slow_stream
    monkeypatch.setattr(search_mod, "ask_graph", fake_graph)

    strategy_model = MagicMock(id="model:strategy")
    answer_model = MagicMock(id="model:answer")
    final_answer_model = MagicMock(id="model:final")

    events: list[dict] = []
    async for raw in search_mod.stream_ask_response(
        question="placeholder",
        strategy_model=strategy_model,
        answer_model=answer_model,
        final_answer_model=final_answer_model,
        corpus_stats={"total_sources": 1, "embedded_sources": 1},
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    types = [e.get("type") for e in events]
    assert "heartbeat" in types, f"expected heartbeat in {types}"
    heartbeats = [e for e in events if e.get("type") == "heartbeat"]
    assert all(
        isinstance(h.get("elapsed_ms"), int) and h.get("stage") == "awaiting_model"
        for h in heartbeats
    )
    assert "final_answer" in types
    assert "complete" in types


@pytest.mark.asyncio
async def test_stream_ask_response_emits_user_visible_status_events(monkeypatch):
    """Ask should expose broad user-readable phases so the UI can show
    immediate and continuous progress instead of a silent loading state."""
    from api.routers import search as search_mod

    monkeypatch.setattr(search_mod, "ASK_STREAM_HEARTBEAT_SECONDS", 5.0)
    monkeypatch.setattr(search_mod, "ASK_LLM_TIMEOUT_SECONDS", 5.0)

    class _Search:
        term = "slurry compatibility"
        instructions = "Find compatibility evidence."

    class _Strategy:
        reasoning = "Need compatibility evidence."
        searches = [_Search()]

    async def _ask_stream(*, input, config=None, version=None):  # noqa: A002
        yield {
            "event": "on_chain_end",
            "name": "agent",
            "data": {"output": {"strategy": _Strategy()}},
        }
        yield {
            "event": "on_chain_end",
            "name": "provide_answer",
            "data": {
                "output": {
                    "retrieved_source_ids": ["source:a"],
                    "answers": ["evidence"],
                }
            },
        }
        yield {
            "event": "on_chain_end",
            "name": "write_final_answer",
            "data": {"output": {"final_answer": "final"}},
        }

    fake_graph = MagicMock()
    fake_graph.astream_events = _ask_stream
    monkeypatch.setattr(search_mod, "ask_graph", fake_graph)

    strategy_model = MagicMock(id="model:strategy")
    answer_model = MagicMock(id="model:answer")
    final_answer_model = MagicMock(id="model:final")

    events: list[dict] = []
    async for raw in search_mod.stream_ask_response(
        question="placeholder",
        strategy_model=strategy_model,
        answer_model=answer_model,
        final_answer_model=final_answer_model,
        corpus_stats={"total_sources": 3, "embedded_sources": 2},
    ):
        if raw.startswith("data: "):
            events.append(json.loads(raw.removeprefix("data: ").strip()))

    status_stages = [
        event.get("stage")
        for event in events
        if event.get("type") == "status"
    ]
    assert status_stages == ["received", "planning", "searching", "writing"]
    assert all(
        isinstance(event.get("elapsed_ms"), int)
        for event in events
        if event.get("type") == "status"
    )
