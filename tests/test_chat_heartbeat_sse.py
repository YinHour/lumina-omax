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


def test_chat_status_sse_event_shape():
    from api.routers import chat

    event = chat.chat_status_sse_event("searching_notebook", "complete", 321)

    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload == {
        "type": "chat_status",
        "stage": "searching_notebook",
        "status": "complete",
        "elapsed_ms": 321,
    }


def test_context_usage_sse_event_shape_and_field_filtering():
    from api.routers import chat

    event = chat.context_usage_sse_event(
        {
            "model_id": "model:test",
            "model_name": "deepseek-v4-pro",
            "provider": "deepseek",
            "input_tokens": 93_400,
            "context_window_tokens": 1_000_000,
            "context_window_source": "builtin",
            "estimated": True,
            "private": "must-not-leak",
        }
    )

    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload == {
        "type": "context_usage",
        "model_id": "model:test",
        "model_name": "deepseek-v4-pro",
        "provider": "deepseek",
        "input_tokens": 93_400,
        "context_window_tokens": 1_000_000,
        "context_window_source": "builtin",
        "estimated": True,
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
async def test_research_stream_emits_tool_activity_sequence(monkeypatch):
    from api.routers import chat

    class _FakeSqliteSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                def __enter__(self_inner):
                    return MagicMock(
                        get_state=lambda config=None: MagicMock(values={"messages": []})
                    )

                def __exit__(self_inner, *args):
                    return False

            return _Ctx()

    class _FakeAsyncSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                async def __aenter__(self_inner):
                    return MagicMock()

                async def __aexit__(self_inner, *args):
                    return False

            return _Ctx()

    monkeypatch.setattr("langgraph.checkpoint.sqlite.SqliteSaver", _FakeSqliteSaver)
    monkeypatch.setattr(
        "langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver", _FakeAsyncSaver
    )

    async def _events(*, input, config=None, version=None):  # noqa: A002
        yield {"event": "on_tool_start", "name": "search_notebook_evidence"}
        yield {"event": "on_tool_end", "name": "search_notebook_evidence"}
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": MagicMock(content="answer")},
        }

    compiled = MagicMock(astream_events=_events)
    state_graph = MagicMock(compile=MagicMock(return_value=compiled))
    monkeypatch.setattr(chat, "build_suggested_questions_event", AsyncMock(return_value=None))

    events = []
    async for raw in chat.stream_chat_response(
        session_id="chat_session:research",
        message="question",
        context={"sources": [], "notes": []},
        state_graph=state_graph,
        checkpoint_file="research.sqlite",
        chat_mode="research",
    ):
        if raw.startswith("data: "):
            events.append(json.loads(raw.removeprefix("data: ").strip()))

    statuses = [
        (event.get("stage"), event.get("status"))
        for event in events
        if event.get("type") == "chat_status"
    ]
    assert statuses[:5] == [
        ("planning", "active"),
        ("searching_notebook", "active"),
        ("searching_notebook", "complete"),
        ("synthesizing", "active"),
        ("model_streaming", "active"),
    ]


@pytest.mark.asyncio
async def test_heartbeat_continues_during_silence_after_first_chunk(monkeypatch):
    from api.routers import chat

    monkeypatch.setattr(chat, "CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(chat, "CHAT_LLM_TIMEOUT_SECONDS", 5.0)

    class _FakeSqliteSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                def __enter__(self_inner):
                    return MagicMock(
                        get_state=lambda config=None: MagicMock(values={"messages": []})
                    )

                def __exit__(self_inner, *args):
                    return False

            return _Ctx()

    class _FakeAsyncSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Ctx:
                async def __aenter__(self_inner):
                    return MagicMock()

                async def __aexit__(self_inner, *args):
                    return False

            return _Ctx()

    monkeypatch.setattr("langgraph.checkpoint.sqlite.SqliteSaver", _FakeSqliteSaver)
    monkeypatch.setattr(
        "langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver", _FakeAsyncSaver
    )

    async def _events(*, input, config=None, version=None):  # noqa: A002
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": MagicMock(content="first")},
        }
        await asyncio.sleep(0.2)
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": MagicMock(content="second")},
        }

    compiled = MagicMock(astream_events=_events)
    state_graph = MagicMock(compile=MagicMock(return_value=compiled))
    monkeypatch.setattr(chat, "build_suggested_questions_event", AsyncMock(return_value=None))

    events = []
    async for raw in chat.stream_chat_response(
        session_id="chat_session:test",
        message="question",
        context={"sources": [], "notes": []},
        state_graph=state_graph,
        checkpoint_file="chat.sqlite",
    ):
        if raw.startswith("data: "):
            events.append(json.loads(raw.removeprefix("data: ").strip()))

    first_index = next(
        index
        for index, event in enumerate(events)
        if event.get("type") == "ai_message" and event.get("content") == "first"
    )
    second_index = next(
        index
        for index, event in enumerate(events)
        if event.get("type") == "ai_message" and event.get("content") == "second"
    )
    assert any(
        event.get("type") == "heartbeat"
        for event in events[first_index + 1 : second_index]
    )


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
