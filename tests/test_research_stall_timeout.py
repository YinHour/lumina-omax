"""Research Agent stall watchdog and independent hard-timeout tests (§57).

Covers:
- stall watchdog cancels a run that makes no effective progress
- effective progress (tool events / model round / answer delta) resets the stall clock
- research hard timeout emits `research_hard_timeout` instead of `llm_timeout`
- quick mode is not affected by the stall watchdog (still `llm_timeout`)
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest


def _patch_savers(monkeypatch):
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


def _collect_events(monkeypatch, graph_events, **kwargs):
    from api.routers import chat

    _patch_savers(monkeypatch)
    monkeypatch.setattr(
        chat, "build_suggested_questions_event", AsyncMock(return_value=None)
    )

    async def _stream(*, input, config=None, version=None):  # noqa: A002
        for event in graph_events:
            yield event
        # keep the generator alive past the test window
        await asyncio.sleep(30)

    compiled = MagicMock(astream_events=_stream)
    state_graph = MagicMock(compile=MagicMock(return_value=compiled))
    monkeypatch.setattr(chat, "CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)

    events = []

    async def _run():
        async for raw in chat.stream_chat_response(
            session_id="chat_session:test",
            message="question",
            context={"sources": [], "notes": []},
            state_graph=state_graph,
            checkpoint_file="test.sqlite",
            chat_mode=kwargs.pop("chat_mode", "research"),
            **kwargs,
        ):
            if raw.startswith("data: "):
                try:
                    events.append(json.loads(raw.removeprefix("data: ").strip()))
                except json.JSONDecodeError:
                    continue

    return _run, events


@pytest.mark.asyncio
async def test_stall_watchdog_emits_research_stall_and_cancels(monkeypatch):
    """A research run with no effective progress must emit `research_stall`
    and must not emit answer_complete / complete afterwards."""
    from api.routers import chat

    monkeypatch.setattr(chat, "RESEARCH_AGENT_STALL_TIMEOUT_SECONDS", 0.15)
    monkeypatch.setattr(chat, "RESEARCH_AGENT_HARD_TIMEOUT_SECONDS", 30.0)

    # Producer yields nothing meaningful: no tool events, no model round, no chunk.
    run, events = _collect_events(monkeypatch, [])
    await run()

    error_event = next((e for e in events if e.get("type") == "error"), None)
    assert error_event is not None
    assert error_event.get("error_code") == "research_stall"
    assert error_event.get("stall_seconds") == 0.15

    types = [e.get("type") for e in events]
    assert "answer_complete" not in types
    assert "complete" not in types


@pytest.mark.asyncio
async def test_stall_watchdog_is_reset_by_tool_events(monkeypatch):
    """Periodic tool events must reset the stall clock so a healthy multi-round
    research run is not cancelled."""
    from api.routers import chat

    monkeypatch.setattr(chat, "RESEARCH_AGENT_STALL_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(chat, "RESEARCH_AGENT_HARD_TIMEOUT_SECONDS", 30.0)

    async def _stream(*, input, config=None, version=None):  # noqa: A002
        # Tool start/end pairs arriving more often than the stall window.
        for i in range(20):
            yield {
                "event": "on_tool_start",
                "name": "search_notebook_evidence",
                "run_id": f"tool-{i}",
            }
            yield {
                "event": "on_tool_end",
                "name": "search_notebook_evidence",
                "run_id": f"tool-{i}",
            }
            await asyncio.sleep(0.05)

    _patch_savers(monkeypatch)
    monkeypatch.setattr(
        chat, "build_suggested_questions_event", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(chat, "CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)

    compiled = MagicMock(astream_events=_stream)
    state_graph = MagicMock(compile=MagicMock(return_value=compiled))

    events = []
    async for raw in chat.stream_chat_response(
        session_id="chat_session:test",
        message="question",
        context={"sources": [], "notes": []},
        state_graph=state_graph,
        checkpoint_file="test.sqlite",
        chat_mode="research",
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    error_events = [e for e in events if e.get("type") == "error"]
    assert not error_events, f"unexpected error events: {error_events}"
    types = [e.get("type") for e in events]
    assert "answer_complete" in types


@pytest.mark.asyncio
async def test_stall_watchdog_is_reset_by_model_round_and_answer_delta(monkeypatch):
    """Model round completion and public answer deltas also count as progress."""
    from api.routers import chat

    monkeypatch.setattr(chat, "RESEARCH_AGENT_STALL_TIMEOUT_SECONDS", 0.4)
    monkeypatch.setattr(chat, "RESEARCH_AGENT_HARD_TIMEOUT_SECONDS", 30.0)

    async def _stream(*, input, config=None, version=None):  # noqa: A002
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": MagicMock(content="partial")},
        }
        await asyncio.sleep(0.1)
        yield {
            "event": "on_chat_model_end",
            "data": {"output": {"content": "partial"}},
        }
        await asyncio.sleep(0.1)
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": MagicMock(content="done")},
        }
        await asyncio.sleep(0.1)
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {
                "output": {
                    "agent": {
                        "messages": MagicMock(content="done"),
                    }
                }
            },
        }

    _patch_savers(monkeypatch)
    monkeypatch.setattr(
        chat, "build_suggested_questions_event", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(chat, "CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)

    compiled = MagicMock(astream_events=_stream)
    state_graph = MagicMock(compile=MagicMock(return_value=compiled))

    events = []
    async for raw in chat.stream_chat_response(
        session_id="chat_session:test",
        message="question",
        context={"sources": [], "notes": []},
        state_graph=state_graph,
        checkpoint_file="test.sqlite",
        chat_mode="research",
    ):
        if raw.startswith("data: "):
            try:
                events.append(json.loads(raw.removeprefix("data: ").strip()))
            except json.JSONDecodeError:
                continue

    error_events = [e for e in events if e.get("type") == "error"]
    assert not error_events, f"unexpected error events: {error_events}"
    types = [e.get("type") for e in events]
    assert "answer_complete" in types


@pytest.mark.asyncio
async def test_research_hard_timeout_uses_research_error_code(monkeypatch):
    """Research must emit `research_hard_timeout` (not `llm_timeout`) when the
    overall hard limit is exceeded."""
    from api.routers import chat

    monkeypatch.setattr(chat, "RESEARCH_AGENT_STALL_TIMEOUT_SECONDS", 30.0)
    monkeypatch.setattr(chat, "RESEARCH_AGENT_HARD_TIMEOUT_SECONDS", 0.15)

    # Producer hangs entirely (no events at all).
    run, events = _collect_events(monkeypatch, [], chat_mode="research")
    await run()

    error_event = next((e for e in events if e.get("type") == "error"), None)
    assert error_event is not None
    assert error_event.get("error_code") == "research_hard_timeout"
    assert error_event.get("timeout_seconds") == 0.15


@pytest.mark.asyncio
async def test_quick_mode_keeps_llm_timeout_and_no_stall_watchdog(monkeypatch):
    """Quick chat must keep the original `llm_timeout` behavior and must not be
    affected by the research stall watchdog."""
    from api.routers import chat

    monkeypatch.setattr(chat, "RESEARCH_AGENT_STALL_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(chat, "RESEARCH_AGENT_HARD_TIMEOUT_SECONDS", 30.0)
    monkeypatch.setattr(chat, "CHAT_LLM_TIMEOUT_SECONDS", 0.15)

    run, events = _collect_events(monkeypatch, [], chat_mode="quick")
    await run()

    error_event = next((e for e in events if e.get("type") == "error"), None)
    assert error_event is not None
    assert error_event.get("error_code") == "llm_timeout"
    assert error_event.get("timeout_seconds") == 0.15


@pytest.mark.asyncio
async def test_stall_watchdog_counts_model_start_and_reasoning_as_progress(monkeypatch):
    """A model round that starts and keeps emitting reasoning chunks must not
    be cancelled: in-flight model calls are real progress (§65)."""
    from api.routers import chat

    monkeypatch.setattr(chat, "RESEARCH_AGENT_STALL_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(chat, "RESEARCH_AGENT_HARD_TIMEOUT_SECONDS", 30.0)

    async def _stream(*, input, config=None, version=None):  # noqa: A002
        yield {"event": "on_chat_model_start", "name": "call_research_model"}
        for i in range(30):
            # reasoning-only chunks keep arriving well past the stall window;
            # the run must not be cancelled while the model is working
            yield {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": MagicMock(
                        content="",
                        additional_kwargs={"reasoning_content": f"thinking step {i}"},
                        response_metadata={},
                    )
                },
            }
            await asyncio.sleep(0.1)
        # generator completes normally - no stall window may have elapsed
        # between chunks, so the watchdog must never fire.

    compiled = MagicMock(astream_events=_stream)
    state_graph = MagicMock(compile=MagicMock(return_value=compiled))
    monkeypatch.setattr(chat, "CHAT_STREAM_HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(
        chat, "build_suggested_questions_event", AsyncMock(return_value=None)
    )

    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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

    monkeypatch.setattr(SqliteSaver, "from_conn_string", _FakeSqliteSaver.from_conn_string)
    monkeypatch.setattr(
        AsyncSqliteSaver, "from_conn_string", _FakeAsyncSaver.from_conn_string
    )

    events = []

    async def _run():
        async for raw in chat.stream_chat_response(
            session_id="chat_session:test",
            message="question",
            context={"sources": [], "notes": []},
            state_graph=state_graph,
            checkpoint_file="test.sqlite",
            chat_mode="research",
        ):
            if raw.startswith("data: "):
                try:
                    events.append(json.loads(raw.removeprefix("data: ").strip()))
                except json.JSONDecodeError:
                    continue

    await _run()

    error_event = next((e for e in events if e.get("type") == "error"), None)
    assert error_event is None, f"research_stall should not fire: {error_event}"
