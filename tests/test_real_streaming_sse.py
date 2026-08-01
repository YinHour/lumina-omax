"""Regression tests for real model deltas versus buffered SSE fallbacks."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


def _decode_events(chunks: list[str]) -> list[dict]:
    return [
        json.loads(chunk.removeprefix("data: ").strip())
        for chunk in chunks
        if chunk.startswith("data: ")
    ]


def _patch_sqlite_savers(monkeypatch) -> None:
    class _FakeSqliteSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Context:
                def __enter__(self):
                    return MagicMock(
                        get_state=lambda config=None: MagicMock(values={"messages": []})
                    )

                def __exit__(self, *args):
                    return False

            return _Context()

    class _FakeAsyncSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class _Context:
                async def __aenter__(self):
                    return MagicMock()

                async def __aexit__(self, *args):
                    return False

            return _Context()

    monkeypatch.setattr("langgraph.checkpoint.sqlite.SqliteSaver", _FakeSqliteSaver)
    monkeypatch.setattr(
        "langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver", _FakeAsyncSaver
    )


async def _collect_chat(monkeypatch, event_stream) -> list[dict]:
    from api.routers import chat

    _patch_sqlite_savers(monkeypatch)
    compiled = MagicMock(astream_events=event_stream)
    state_graph = MagicMock(compile=MagicMock(return_value=compiled))
    monkeypatch.setattr(
        chat, "build_suggested_questions_event", AsyncMock(return_value=None)
    )

    chunks = [
        chunk
        async for chunk in chat.stream_chat_response(
            session_id="chat_session:streaming",
            message="question",
            context={"sources": [], "notes": []},
            state_graph=state_graph,
            checkpoint_file="streaming.sqlite",
        )
    ]
    return _decode_events(chunks)


@pytest.mark.asyncio
async def test_chat_marks_provider_chunks_as_real_deltas(monkeypatch):
    async def _events(*, input, config=None, version=None):  # noqa: A002
        for content in ("Hel", "lo"):
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content=content)},
            }
        yield {
            "event": "on_chat_model_end",
            "data": {"output": {"content": "Hello"}},
        }

    events = await _collect_chat(monkeypatch, _events)
    ai_events = [event for event in events if event.get("type") == "ai_message"]

    assert [(event["content"], event["stream_mode"]) for event in ai_events] == [
        ("Hel", "delta"),
        ("lo", "delta"),
    ]


@pytest.mark.asyncio
async def test_chat_emits_non_streaming_provider_result_once(monkeypatch):
    content = "buffered-" * 20

    async def _events(*, input, config=None, version=None):  # noqa: A002
        yield {
            "event": "on_chat_model_end",
            "data": {"output": {"content": content}},
        }

    events = await _collect_chat(monkeypatch, _events)
    ai_events = [event for event in events if event.get("type") == "ai_message"]

    assert ai_events == [
        {
            "type": "ai_message",
            "content": content,
            "timestamp": None,
            "stream_mode": "buffered",
        }
    ]


@pytest.mark.asyncio
async def test_chat_separates_reasoning_without_exposing_raw_content(monkeypatch):
    async def _events(*, input, config=None, version=None):  # noqa: A002
        yield {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": MagicMock(
                    content="",
                    additional_kwargs={"reasoning_content": "private reasoning"},
                )
            },
        }
        for content in ("<think>hidden", " analysis</think>Vis", "ible answer"):
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content=content)},
            }

    events = await _collect_chat(monkeypatch, _events)
    reasoning_events = [
        event for event in events if event.get("type") == "reasoning_status"
    ]
    ai_events = [event for event in events if event.get("type") == "ai_message"]

    assert reasoning_events == [{"type": "reasoning_status", "status": "active"}]
    assert [event["content"] for event in ai_events] == ["Vis", "ible answer"]
    assert "private reasoning" not in json.dumps(events)
    assert "hidden analysis" not in json.dumps(events)


async def _collect_source_chat(monkeypatch, event_stream) -> list[dict]:
    from api.routers import source_chat

    _patch_sqlite_savers(monkeypatch)
    compiled = MagicMock(astream_events=event_stream)
    monkeypatch.setattr(
        source_chat.source_chat_state,
        "compile",
        MagicMock(return_value=compiled),
    )

    chunks = [
        chunk
        async for chunk in source_chat.stream_source_chat_response(
            session_id="chat_session:streaming",
            source_id="source:streaming",
            message="question",
        )
    ]
    return _decode_events(chunks)


@pytest.mark.asyncio
async def test_source_chat_distinguishes_deltas_from_buffered_fallback(monkeypatch):
    async def _delta_events(*, input, config=None, version=None):  # noqa: A002
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": MagicMock(content="real delta")},
        }

    delta_events = await _collect_source_chat(monkeypatch, _delta_events)
    delta_ai = [event for event in delta_events if event.get("type") == "ai_message"]
    assert [(event["content"], event["stream_mode"]) for event in delta_ai] == [
        ("real delta", "delta")
    ]

    content = "complete provider response"

    async def _buffered_events(*, input, config=None, version=None):  # noqa: A002
        yield {
            "event": "on_chat_model_end",
            "data": {"output": {"content": content}},
        }

    buffered_events = await _collect_source_chat(monkeypatch, _buffered_events)
    buffered_ai = [
        event for event in buffered_events if event.get("type") == "ai_message"
    ]
    assert [(event["content"], event["stream_mode"]) for event in buffered_ai] == [
        (content, "buffered")
    ]


@pytest.mark.asyncio
async def test_source_chat_emits_safe_reasoning_status_before_visible_answer(
    monkeypatch,
):
    async def _events(*, input, config=None, version=None):  # noqa: A002
        yield {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": MagicMock(
                    content="",
                    additional_kwargs={"reasoning_content": "do not expose"},
                )
            },
        }
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": MagicMock(content="Public answer")},
        }

    events = await _collect_source_chat(monkeypatch, _events)

    assert [
        event["type"]
        for event in events
        if event.get("type") in {"reasoning_status", "ai_message"}
    ] == ["reasoning_status", "ai_message"]
    assert "do not expose" not in json.dumps(events)
