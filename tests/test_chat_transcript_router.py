from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from api.chat_transcript_service import TranscriptPage
from api.routers import chat


@pytest.mark.asyncio
async def test_initialized_session_detail_uses_transcript_page_without_checkpoint_scan(
    monkeypatch,
):
    session = SimpleNamespace(
        id="chat_session:1",
        title="Long session",
        created="2026-07-11T00:00:00Z",
        updated="2026-07-11T01:00:00Z",
        mode="quick",
        model_override=None,
        transcript_initialized=True,
        message_count=120,
    )
    monkeypatch.setattr(chat.ChatSession, "get", AsyncMock(return_value=session))
    monkeypatch.setattr(
        chat,
        "get_transcript_page",
        AsyncMock(
            return_value=TranscriptPage(
                messages=[
                    {
                        "message_id": "m71",
                        "role": "human",
                        "content": "Question 36",
                        "sequence": 71,
                    },
                    {
                        "message_id": "m72",
                        "role": "ai",
                        "content": "Answer 36",
                        "sequence": 72,
                    },
                ],
                has_more=True,
                next_cursor=71,
            )
        ),
    )
    monkeypatch.setattr(
        chat,
        "repo_query",
        AsyncMock(return_value=[{"out": "notebook:1"}]),
    )
    checkpoint_count = AsyncMock()
    monkeypatch.setattr(chat, "get_session_message_count", checkpoint_count)

    response = await chat.get_session(
        "chat_session:1",
        limit=2,
        before_sequence=73,
    )

    assert response.message_count == 120
    assert [message.id for message in response.messages] == ["m71", "m72"]
    assert response.has_more is True
    assert response.next_cursor == 71
    checkpoint_count.assert_not_awaited()
    chat.get_transcript_page.assert_awaited_once_with(
        "chat_session:1",
        limit=2,
        before_sequence=73,
    )
