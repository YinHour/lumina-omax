"""Tests for chat suggested-question SSE helpers."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_build_suggested_questions_event_returns_sse(monkeypatch):
    from api.routers import chat

    monkeypatch.setattr(
        chat,
        "generate_followup_questions",
        AsyncMock(return_value=["Q1?", "Q2?", "Q3?"]),
    )

    event = await chat.build_suggested_questions_event(
        answer="AI answer",
        context={"sources": []},
        model_override=None,
    )

    assert event is not None
    assert event.startswith("data: ")
    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload == {"type": "suggested_questions", "questions": ["Q1?", "Q2?", "Q3?"]}


@pytest.mark.asyncio
async def test_build_suggested_questions_event_returns_fallback_on_failure(monkeypatch):
    from api.routers import chat

    generate = AsyncMock(side_effect=RuntimeError("provider failed"))
    monkeypatch.setattr(chat, "generate_followup_questions", generate)

    event = await chat.build_suggested_questions_event(
        answer="AI answer",
        context={"sources": []},
        model_override=None,
    )

    assert event is not None
    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload["type"] == "suggested_questions"
    assert len(payload["questions"]) == 3


@pytest.mark.asyncio
async def test_build_suggested_questions_event_returns_fallback_for_wrong_count(monkeypatch):
    from api.routers import chat

    monkeypatch.setattr(
        chat,
        "generate_followup_questions",
        AsyncMock(return_value=["Only one?"]),
    )

    event = await chat.build_suggested_questions_event(
        answer="AI answer",
        context={"sources": []},
        model_override=None,
    )

    assert event is not None
    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload["type"] == "suggested_questions"
    assert len(payload["questions"]) == 3


@pytest.mark.asyncio
async def test_build_suggested_questions_event_returns_fallback_on_timeout(monkeypatch):
    from api.routers import chat

    async def slow_generate(*args, **kwargs):
        await asyncio.sleep(0.05)
        return ["Q1?", "Q2?", "Q3?"]

    monkeypatch.setattr(chat, "generate_followup_questions", slow_generate)
    monkeypatch.setattr(chat, "SUGGESTED_QUESTIONS_TIMEOUT_SECONDS", 0.01)

    event = await chat.build_suggested_questions_event(
        answer="AI answer",
        context={"sources": []},
        model_override=None,
    )

    assert event is not None
    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload["type"] == "suggested_questions"
    assert len(payload["questions"]) == 3
