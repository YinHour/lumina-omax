"""Tests for notebook guide API route wrappers."""

from unittest.mock import AsyncMock

import pytest

from api.models import NotebookGuideResponse


@pytest.mark.asyncio
async def test_get_notebook_guide_route_uses_service(monkeypatch):
    from api.routers import notebooks

    expected = NotebookGuideResponse(
        notebook_id="notebook:1",
        source_count=1,
        generated_at="2026-06-11T00:00:00Z",
        summary="Summary",
        questions=["Q1?", "Q2?", "Q3?"],
        status="ready",
    )
    generate = AsyncMock(return_value=expected)
    monkeypatch.setattr(notebooks, "generate_notebook_guide", generate)

    result = await notebooks.get_notebook_guide("notebook:1")

    assert result == expected
    generate.assert_awaited_once_with("notebook:1", force=False)


@pytest.mark.asyncio
async def test_regenerate_notebook_guide_route_forces_service(monkeypatch):
    from api.routers import notebooks

    expected = NotebookGuideResponse(
        notebook_id="notebook:1",
        source_count=1,
        generated_at="2026-06-11T00:00:00Z",
        summary="Summary",
        questions=["Q1?", "Q2?", "Q3?"],
        status="ready",
    )
    generate = AsyncMock(return_value=expected)
    monkeypatch.setattr(notebooks, "generate_notebook_guide", generate)

    result = await notebooks.regenerate_notebook_guide("notebook:1")

    assert result == expected
    generate.assert_awaited_once_with("notebook:1", force=True)
