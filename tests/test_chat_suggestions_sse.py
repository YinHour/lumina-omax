"""Tests for chat suggested-question SSE helpers."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest


def test_answer_complete_sse_event_returns_done_event():
    from api.routers import chat

    event = chat.answer_complete_sse_event()

    assert event.startswith("data: ")
    payload = json.loads(event.removeprefix("data: ").strip())
    assert payload == {"type": "answer_complete"}


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
async def test_build_suggested_questions_event_passes_question_to_generator(monkeypatch):
    from api.routers import chat

    generate = AsyncMock(return_value=["Q1?", "Q2?", "Q3?"])
    monkeypatch.setattr(chat, "generate_followup_questions", generate)

    await chat.build_suggested_questions_event(
        question="What changed in the slurry behavior?",
        answer="AI answer",
        context={"sources": []},
        model_override=None,
    )

    generate.assert_awaited_once_with(
        question="What changed in the slurry behavior?",
        answer="AI answer",
        context={"sources": []},
        model_override=None,
        raise_on_parse_error=True,
    )


@pytest.mark.asyncio
async def test_build_suggested_questions_event_logs_empty_and_fallback(monkeypatch):
    from api.routers import chat

    logged_steps: list[str] = []
    monkeypatch.setattr(
        chat,
        "generate_followup_questions",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        chat,
        "log_chat_info",
        lambda trace_id, step, **fields: logged_steps.append(step),
    )

    event = await chat.build_suggested_questions_event(
        question="What changed in the slurry behavior?",
        answer="AI answer",
        context={"sources": []},
        model_override=None,
        trace_id="trace-1",
    )

    payload = json.loads(event.removeprefix("data: ").strip())
    assert len(payload["questions"]) == 3
    assert "suggestions_start" in logged_steps
    assert "suggestions_empty" in logged_steps
    assert "suggestions_fallback" in logged_steps


@pytest.mark.asyncio
async def test_build_suggested_questions_event_logs_parse_failed(monkeypatch):
    from api.notebook_guide_service import FollowupQuestionParseError
    from api.routers import chat

    logged_steps: list[str] = []
    monkeypatch.setattr(
        chat,
        "generate_followup_questions",
        AsyncMock(side_effect=FollowupQuestionParseError("bad JSON")),
    )
    monkeypatch.setattr(
        chat,
        "log_chat_info",
        lambda trace_id, step, **fields: logged_steps.append(step),
    )

    event = await chat.build_suggested_questions_event(
        question="What changed in the slurry behavior?",
        answer="AI answer",
        context={"sources": []},
        model_override=None,
        trace_id="trace-1",
    )

    payload = json.loads(event.removeprefix("data: ").strip())
    assert len(payload["questions"]) == 3
    assert "suggestions_parse_failed" in logged_steps
    assert "suggestions_fallback" in logged_steps


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
