"""Tests for chat SSE heartbeat + LLM timeout instrumentation.

These tests cover the A-layer behaviour added in §29:

- heartbeat SSE event shape and helper
- producer/heartbeat interleaving while waiting for the first model byte
- llm_timeout error event when the producer exceeds CHAT_LLM_TIMEOUT_SECONDS
"""

import asyncio
import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def test_heartbeat_sse_event_shape():
    from api.routers import chat

    event = chat.heartbeat_sse_event("awaiting_model", 12345)

    assert event.startswith("data: ")
    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload == {
        "type": "heartbeat",
        "stage": "awaiting_model",
        "elapsed_ms": 12345,
    }


def test_env_positive_float_falls_back_on_invalid(monkeypatch):
    from api.routers import chat

    monkeypatch.setenv("CHAT_LLM_TIMEOUT_TEST", "not-a-number")
    assert chat._env_positive_float("CHAT_LLM_TIMEOUT_TEST", 7.5) == 7.5

    monkeypatch.setenv("CHAT_LLM_TIMEOUT_TEST", "0")
    assert chat._env_positive_float("CHAT_LLM_TIMEOUT_TEST", 7.5) == 7.5

    monkeypatch.setenv("CHAT_LLM_TIMEOUT_TEST", "12.5")
    assert chat._env_positive_float("CHAT_LLM_TIMEOUT_TEST", 7.5) == 12.5


def _set_default_imports(monkeypatch, *, raise_after_seconds: float | None = None, chunks: list[str] | None = None) -> None:
    """Patch heavy chat-streaming dependencies with a controllable async fake."""
    from api.routers import chat as chat_mod

    # Stub out checkpoint saver bookkeeping.
    class _FakeSqliteSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                def __enter__(self_inner):
                    return MagicMock(get_state=lambda config=None: MagicMock(values={"messages": []}))
                def __exit__(self_inner, *args):
                    return False
            return _Ctx()

    monkeypatch.setattr(
        "langgraph.checkpoint.sqlite.SqliteSaver",
        _FakeSqliteSaver,
    )

    class _FakeAsyncSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                async def __aenter__(self_inner):
                    return MagicMock()
                async def __aexit__(self_inner, *args):
                    return False
            return _Ctx()

    monkeypatch.setattr(
        "langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver",
        _FakeAsyncSaver,
    )

    async def _fake_astream_events(input, config=None, version=None):  # noqa: A002 - mirror sig
        if raise_after_seconds is not None:
            await asyncio.sleep(raise_after_seconds)
            return
        if chunks:
            for chunk_text in chunks:
                yield {
                    "event": "on_chat_model_stream",
                    "data": {
                        "chunk": MagicMock(content=chunk_text),
                    },
                }

    fake_graph = MagicMock()
    fake_graph.astream_events = _fake_astream_events
    monkeypatch.setattr(
        chat_mod.agent_state, "compile", MagicMock(return_value=fake_graph)
    )


@pytest.mark.asyncio
async def test_stream_chat_response_emits_heartbeats_before_first_chunk(monkeypatch):
    """When the model is slow to return the first chunk, the SSE stream must
    surface heartbeat events so the UI knows the server is still working."""
    from api.routers import chat as chat_mod

    # Shrink intervals to keep the test fast and bounded.
    monkeypatch.setattr(chat_mod, "CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(chat_mod, "CHAT_LLM_TIMEOUT_SECONDS", 5.0)

    # Delay before any chunk + one chunk so we have first_ai_chunk + answer_complete.
    chunks_after_delay: list[str] = ["hello", " world"]

    from api.routers import chat as chat_mod2
    chat_mod_local: Any = chat_mod2

    class _FakeSqliteSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                def __enter__(self_inner):
                    return MagicMock(get_state=lambda config=None: MagicMock(values={"messages": []}))
                def __exit__(self_inner, *a):
                    return False
            return _Ctx()

    monkeypatch.setattr("langgraph.checkpoint.sqlite.SqliteSaver", _FakeSqliteSaver)

    class _FakeAsyncSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                async def __aenter__(self_inner):
                    return MagicMock()
                async def __aexit__(self_inner, *a):
                    return False
            return _Ctx()

    monkeypatch.setattr(
        "langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver", _FakeAsyncSaver
    )

    async def _fake_astream_events(*, input, config=None, version=None):  # noqa: A002
        # Sleep long enough to allow several heartbeats (5 * 0.05s = 0.25s).
        await asyncio.sleep(0.25)
        for ch in chunks_after_delay:
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content=ch)},
            }

    fake_graph = MagicMock()
    fake_graph.astream_events = _fake_astream_events
    monkeypatch.setattr(
        chat_mod_local.agent_state, "compile", MagicMock(return_value=fake_graph)
    )

    # Stub suggested-question generator so we don't hit any real provider.
    monkeypatch.setattr(
        chat_mod_local,
        "build_suggested_questions_event",
        AsyncMock(return_value=None),
    )

    events: list[dict] = []
    async for raw in chat_mod_local.stream_chat_response(
        session_id="chat_session:test",
        message="hi",
        context={"sources": [], "notes": []},
        model_override=None,
        enable_web_search=False,
        trace_id="hbtest",
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    types = [evt.get("type") for evt in events]
    assert "heartbeat" in types, f"expected at least one heartbeat in {types}"
    # Heartbeats must arrive before the first ai_message chunk.
    first_ai_idx = types.index("ai_message")
    first_hb_idx = types.index("heartbeat")
    assert first_hb_idx < first_ai_idx
    assert "answer_complete" in types
    heartbeat_events = [e for e in events if e.get("type") == "heartbeat"]
    assert all(e.get("stage") == "awaiting_model" for e in heartbeat_events)
    assert all(isinstance(e.get("elapsed_ms"), int) for e in heartbeat_events)


@pytest.mark.asyncio
async def test_stream_chat_response_emits_llm_timeout_event(monkeypatch):
    """If the producer never yields a chunk before CHAT_LLM_TIMEOUT_SECONDS,
    the SSE stream must emit an error event with error_code=llm_timeout."""
    from api.routers import chat as chat_mod

    monkeypatch.setattr(chat_mod, "CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(chat_mod, "CHAT_LLM_TIMEOUT_SECONDS", 0.15)

    class _FakeSqliteSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                def __enter__(self_inner):
                    return MagicMock(get_state=lambda config=None: MagicMock(values={"messages": []}))
                def __exit__(self_inner, *a):
                    return False
            return _Ctx()

    monkeypatch.setattr("langgraph.checkpoint.sqlite.SqliteSaver", _FakeSqliteSaver)

    class _FakeAsyncSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                async def __aenter__(self_inner):
                    return MagicMock()
                async def __aexit__(self_inner, *a):
                    return False
            return _Ctx()

    monkeypatch.setattr(
        "langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver", _FakeAsyncSaver
    )

    async def _hanging_stream(*, input, config=None, version=None):  # noqa: A002
        # Sleep longer than the timeout; never yield a chunk.
        await asyncio.sleep(2.0)
        if False:
            yield {}  # pragma: no cover - keeps function a generator

    fake_graph = MagicMock()
    fake_graph.astream_events = _hanging_stream
    monkeypatch.setattr(
        chat_mod.agent_state, "compile", MagicMock(return_value=fake_graph)
    )

    monkeypatch.setattr(
        chat_mod,
        "build_suggested_questions_event",
        AsyncMock(return_value=None),
    )

    events: list[dict] = []
    async for raw in chat_mod.stream_chat_response(
        session_id="chat_session:test",
        message="hi",
        context={"sources": [], "notes": []},
        model_override=None,
        enable_web_search=False,
        trace_id="totest",
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    # Should NOT contain ai_message / answer_complete.
    types = [evt.get("type") for evt in events]
    assert "ai_message" not in types
    assert "answer_complete" not in types

    timeout_event = next((e for e in events if e.get("type") == "error"), None)
    assert timeout_event is not None
    assert timeout_event.get("error_code") == "llm_timeout"
    assert timeout_event.get("timeout_seconds") == 0.15
    assert "timed out" in (timeout_event.get("message") or "").lower()


def test_chat_error_code_from_exception_known_classes():
    from api.routers import chat
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

    assert chat.chat_error_code_from_exception(AuthenticationError) == "authentication"
    assert chat.chat_error_code_from_exception(RateLimitError) == "rate_limit"
    assert chat.chat_error_code_from_exception(ConfigurationError) == "configuration"
    assert chat.chat_error_code_from_exception(NetworkError) == "network"
    assert chat.chat_error_code_from_exception(ExternalServiceError) == "external_service"
    assert chat.chat_error_code_from_exception(InvalidInputError) == "invalid_input"
    assert chat.chat_error_code_from_exception(NotFoundError) == "not_found"
    assert chat.chat_error_code_from_exception(OpenNotebookError) == "internal_error"


def test_chat_error_code_from_exception_unknown_falls_back():
    from api.routers import chat

    class _SomeBespokeError(Exception):
        pass

    assert chat.chat_error_code_from_exception(_SomeBespokeError) == "internal_error"
    # Plain Exception also maps to internal_error.
    assert chat.chat_error_code_from_exception(Exception) == "internal_error"


@pytest.mark.asyncio
async def test_stream_chat_response_emits_error_code_for_rate_limit(monkeypatch):
    """When the producer raises a RateLimitError, the SSE error event must
    carry a stable wire ``error_code`` so the front-end can pick the right
    localized bubble template."""
    from api.routers import chat as chat_mod
    from open_notebook.exceptions import RateLimitError

    monkeypatch.setattr(chat_mod, "CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(chat_mod, "CHAT_LLM_TIMEOUT_SECONDS", 5.0)

    class _FakeSqliteSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                def __enter__(self_inner):
                    return MagicMock(get_state=lambda config=None: MagicMock(values={"messages": []}))
                def __exit__(self_inner, *a):
                    return False
            return _Ctx()

    monkeypatch.setattr("langgraph.checkpoint.sqlite.SqliteSaver", _FakeSqliteSaver)

    class _FakeAsyncSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                async def __aenter__(self_inner):
                    return MagicMock()
                async def __aexit__(self_inner, *a):
                    return False
            return _Ctx()

    monkeypatch.setattr(
        "langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver", _FakeAsyncSaver
    )

    async def _raising_stream(*, input, config=None, version=None):  # noqa: A002
        raise RateLimitError(
            "Rate limit exceeded. Please wait a moment and try again."
        )
        if False:
            yield {}  # pragma: no cover

    fake_graph = MagicMock()
    fake_graph.astream_events = _raising_stream
    monkeypatch.setattr(
        chat_mod.agent_state, "compile", MagicMock(return_value=fake_graph)
    )

    monkeypatch.setattr(
        chat_mod,
        "build_suggested_questions_event",
        AsyncMock(return_value=None),
    )

    events: list[dict] = []
    async for raw in chat_mod.stream_chat_response(
        session_id="chat_session:test",
        message="hi",
        context={"sources": [], "notes": []},
        model_override=None,
        enable_web_search=False,
        trace_id="errtest",
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    error_event = next((e for e in events if e.get("type") == "error"), None)
    assert error_event is not None
    assert error_event.get("error_code") == "rate_limit"
    # Should NOT have a llm_timeout-specific field on a generic error.
    assert "timeout_seconds" not in error_event
    assert "rate limit" in (error_event.get("message") or "").lower()
