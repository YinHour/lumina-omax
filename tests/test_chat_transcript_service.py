from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from api import chat_transcript_service as transcript


def test_visible_checkpoint_messages_excludes_tool_protocol_and_thinking():
    messages = [
        HumanMessage(content="Question", id="human-1"),
        AIMessage(
            content="",
            id="tool-call-1",
            tool_calls=[{"id": "call-1", "name": "search", "args": {}}],
        ),
        ToolMessage(content="large private tool result", tool_call_id="call-1"),
        AIMessage(content="<think>hidden</think>Visible answer", id="ai-1"),
    ]

    visible = transcript.visible_checkpoint_messages(messages)

    assert [(row["role"], row["content"]) for row in visible] == [
        ("human", "Question"),
        ("ai", "Visible answer"),
    ]


@pytest.mark.asyncio
async def test_persist_chat_turn_writes_messages_before_marking_session_saved(
    monkeypatch,
):
    calls: list[str] = []

    async def upsert(_session_id, rows):
        calls.append("messages")
        assert [row["role"] for row in rows] == ["human", "ai"]

    async def metadata(_session_id, **kwargs):
        calls.append("metadata")
        assert kwargs["last_message_preview"] == "Answer"
        return 2

    monkeypatch.setattr(transcript, "_upsert_messages", upsert)
    monkeypatch.setattr(transcript, "_update_session_metadata", metadata)

    saved = await transcript.persist_chat_turn(
        "chat_session:1",
        trace_id="trace-1",
        user_content="Question",
        ai_content="Answer",
    )

    assert saved is True
    assert calls == ["messages", "metadata"]


@pytest.mark.asyncio
async def test_get_transcript_page_returns_oldest_to_newest_with_cursor(monkeypatch):
    rows = [
        {"message_id": "m5", "role": "human", "content": "5", "sequence": 5},
        {"message_id": "m4", "role": "ai", "content": "4", "sequence": 4},
        {"message_id": "m3", "role": "human", "content": "3", "sequence": 3},
    ]
    query = AsyncMock(return_value=rows)
    monkeypatch.setattr(transcript, "repo_query", query)

    page = await transcript.get_transcript_page("chat_session:1", limit=2)

    assert [row["message_id"] for row in page.messages] == ["m4", "m5"]
    assert page.has_more is True
    assert page.next_cursor == 4


@pytest.mark.asyncio
async def test_failed_legacy_backfill_does_not_mark_transcript_initialized(monkeypatch):
    monkeypatch.setattr(
        transcript,
        "_upsert_messages",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    )
    update_metadata = AsyncMock()
    monkeypatch.setattr(transcript, "_update_session_metadata", update_metadata)

    initialized = await transcript.ensure_transcript_initialized(
        "chat_session:1",
        [HumanMessage(content="Question", id="human-1")],
    )

    assert initialized is False
    update_metadata.assert_not_awaited()


@pytest.mark.asyncio
async def test_checkpoint_compaction_keeps_recent_messages_and_summarizes_old_turns(
    monkeypatch,
):
    messages = [
        HumanMessage(content="Old question", id="h1"),
        AIMessage(content="Old answer", id="a1"),
        HumanMessage(content="Recent question", id="h2"),
        AIMessage(content="Recent answer", id="a2"),
    ]
    update_state = AsyncMock()
    compiled = SimpleNamespace(
        aget_state=AsyncMock(return_value=SimpleNamespace(values={"messages": messages})),
        aupdate_state=update_state,
    )
    state_graph = MagicMock()
    state_graph.compile.return_value = compiled

    class FakeSaver:
        @classmethod
        def from_conn_string(cls, _path):
            class Context:
                async def __aenter__(self):
                    return MagicMock()

                async def __aexit__(self, *args):
                    return False

            return Context()

    monkeypatch.setattr(transcript, "AsyncSqliteSaver", FakeSaver)
    monkeypatch.setenv("CHAT_HISTORY_MAX_MESSAGES", "2")
    monkeypatch.setenv("CHAT_HISTORY_MAX_TOKENS", "16000")

    compacted = await transcript.compact_chat_checkpoint(
        "chat_session:1",
        state_graph=state_graph,
        checkpoint_file="checkpoint.sqlite",
        chat_mode="quick",
    )

    assert compacted is True
    update = update_state.await_args.args[1]
    assert {message.id for message in update["messages"]} == {"h1", "a1"}
    assert "Old question" in update["conversation_summary"]
    assert "Old answer" in update["conversation_summary"]
