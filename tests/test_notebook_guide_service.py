"""Tests for notebook guide and suggested question generation."""

from unittest.mock import AsyncMock

import pytest

from api.models import NotebookGuideResponse


class FakeModel:
    def __init__(self, content: str):
        self.content = content

    async def ainvoke(self, _messages):
        return type("Message", (), {"content": self.content})()


@pytest.mark.asyncio
async def test_empty_notebook_guide_when_no_processed_sources(monkeypatch):
    from api import notebook_guide_service as service

    monkeypatch.setattr(service, "repo_query", AsyncMock(return_value=[]))

    guide = await service.generate_notebook_guide("notebook:empty")

    assert isinstance(guide, NotebookGuideResponse)
    assert guide.status == "empty"
    assert guide.source_count == 0
    assert guide.summary is None
    assert guide.questions == []


@pytest.mark.asyncio
async def test_matching_cached_notebook_guide_is_reused(monkeypatch):
    from api import notebook_guide_service as service

    sources = [
        {
            "id": "source:1",
            "title": "A",
            "full_text": "processed text",
            "updated": "2026-06-11 10:00:00",
        }
    ]
    fingerprint = service.build_source_fingerprint(sources)
    repo_query = AsyncMock(
        side_effect=[
            [{"source": sources[0]}],
            [
                {
                    "id": "notebook_guide:cached",
                    "source_fingerprint": fingerprint,
                    "source_count": 1,
                    "summary": "Cached summary",
                    "questions": ["Q1?", "Q2?", "Q3?"],
                    "updated": "2026-06-11 10:30:00",
                }
            ],
        ]
    )
    provision = AsyncMock()

    monkeypatch.setattr(service, "repo_query", repo_query)
    monkeypatch.setattr(service, "provision_langchain_model", provision)

    guide = await service.generate_notebook_guide("notebook:cached")

    assert guide.status == "ready"
    assert guide.summary == "Cached summary"
    assert guide.questions == ["Q1?", "Q2?", "Q3?"]
    provision.assert_not_awaited()


@pytest.mark.asyncio
async def test_generated_notebook_guide_has_exactly_three_questions(monkeypatch):
    from api import notebook_guide_service as service

    sources = [
        {
            "id": "source:1",
            "title": "A",
            "full_text": "This source discusses oilfield chemistry experiments.",
            "updated": "2026-06-11 10:00:00",
        }
    ]
    repo_query = AsyncMock(side_effect=[[{"source": sources[0]}], []])
    repo_create = AsyncMock(return_value={"id": "notebook_guide:new"})
    model = FakeModel(
        '{"summary":"Generated summary","questions":["Q1?","Q2?","Q3?","Q4?"]}'
    )

    monkeypatch.setattr(service, "repo_query", repo_query)
    monkeypatch.setattr(service, "repo_create", repo_create)
    monkeypatch.setattr(service, "provision_langchain_model", AsyncMock(return_value=model))

    guide = await service.generate_notebook_guide("notebook:new")

    assert guide.status == "ready"
    assert guide.summary == "Generated summary"
    assert guide.questions == ["Q1?", "Q2?", "Q3?"]
    repo_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_malformed_followup_json_returns_empty_questions(monkeypatch):
    from api import notebook_guide_service as service

    model = FakeModel("not json")
    monkeypatch.setattr(service, "provision_langchain_model", AsyncMock(return_value=model))

    questions = await service.generate_followup_questions(
        answer="The answer discussed mechanism risks.",
        context={"sources": []},
    )

    assert questions == []


@pytest.mark.asyncio
async def test_malformed_followup_json_raises_when_requested(monkeypatch):
    from api import notebook_guide_service as service

    model = FakeModel("not json")
    monkeypatch.setattr(service, "provision_langchain_model", AsyncMock(return_value=model))

    with pytest.raises(service.FollowupQuestionParseError):
        await service.generate_followup_questions(
            question="What changed?",
            answer="The answer discussed mechanism risks.",
            context={"sources": []},
            raise_on_parse_error=True,
        )


@pytest.mark.asyncio
async def test_empty_followup_model_output_returns_empty_when_requested(monkeypatch):
    from api import notebook_guide_service as service

    model = FakeModel("")
    monkeypatch.setattr(service, "provision_langchain_model", AsyncMock(return_value=model))

    questions = await service.generate_followup_questions(
        question="What changed?",
        answer="The answer discussed mechanism risks.",
        context={"sources": []},
        raise_on_parse_error=True,
    )

    assert questions == []
