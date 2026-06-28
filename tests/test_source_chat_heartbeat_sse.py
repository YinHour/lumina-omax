"""Tests for source chat SSE heartbeat + llm_timeout + error_code wiring (§32)."""

import asyncio
import json
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_stream_source_chat_emits_error_code_for_rate_limit(monkeypatch):
    """Verify source chat surfaces an SSE error event with a stable wire
    ``error_code`` when the underlying graph raises a typed exception."""
    from api.routers import source_chat as source_chat_mod
    from open_notebook.exceptions import RateLimitError

    monkeypatch.setattr(source_chat_mod, "SOURCE_CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(source_chat_mod, "SOURCE_CHAT_LLM_TIMEOUT_SECONDS", 5.0)

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
        raise RateLimitError("Rate limit exceeded. Try later.")
        if False:
            yield {}  # pragma: no cover

    fake_graph = MagicMock()
    fake_graph.astream_events = _raising_stream
    monkeypatch.setattr(
        source_chat_mod.source_chat_state, "compile", MagicMock(return_value=fake_graph)
    )

    events: list[dict] = []
    async for raw in source_chat_mod.stream_source_chat_response(
        session_id="chat_session:test",
        source_id="source:test",
        message="hi",
        model_override=None,
        enable_web_search=False,
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    types = [e.get("type") for e in events]
    assert "user_message" in types
    error_event = next((e for e in events if e.get("type") == "error"), None)
    assert error_event is not None, f"expected error event in {events}"
    assert error_event.get("error_code") == "rate_limit"
    assert "rate limit" in (error_event.get("message") or "").lower()


@pytest.mark.asyncio
async def test_stream_source_chat_emits_llm_timeout_when_producer_hangs(monkeypatch):
    """Source chat must surface a structured ``llm_timeout`` SSE event when the
    graph fails to yield any chunk before ``SOURCE_CHAT_LLM_TIMEOUT_SECONDS``."""
    from api.routers import source_chat as source_chat_mod

    monkeypatch.setattr(source_chat_mod, "SOURCE_CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(source_chat_mod, "SOURCE_CHAT_LLM_TIMEOUT_SECONDS", 0.15)

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
        await asyncio.sleep(2.0)
        if False:
            yield {}  # pragma: no cover

    fake_graph = MagicMock()
    fake_graph.astream_events = _hanging_stream
    monkeypatch.setattr(
        source_chat_mod.source_chat_state, "compile", MagicMock(return_value=fake_graph)
    )

    events: list[dict] = []
    async for raw in source_chat_mod.stream_source_chat_response(
        session_id="chat_session:test",
        source_id="source:test",
        message="hi",
        model_override=None,
        enable_web_search=False,
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    types = [e.get("type") for e in events]
    timeout_event = next((e for e in events if e.get("type") == "error"), None)
    assert timeout_event is not None
    assert timeout_event.get("error_code") == "llm_timeout"
    assert timeout_event.get("timeout_seconds") == 0.15
    # Should not have emitted "ai_message" or "complete" since the producer
    # never produced anything before the timeout cancellation.
    assert "ai_message" not in types
    assert "complete" not in types
