"""Tests for text_search BM25 + substring fallback merge behavior.

The BM25 analyzer has no Chinese tokenizer, so continuous CJK terms are
indexed as single tokens and substring queries miss them. text_search()
appends substring matches (title/full_text/insight/note) so Chinese terms
surface the same way the sources list filter does.
"""

from unittest.mock import AsyncMock, patch

import pytest

from open_notebook.domain.notebook import text_search


def _bm25_result(rid: str, relevance: float) -> dict:
    return {
        "id": rid,
        "parent_id": rid,
        "title": f"title-{rid}",
        "relevance": relevance,
    }


def _substring_result(rid: str) -> dict:
    return {
        "id": rid,
        "parent_id": rid,
        "title": f"title-{rid}",
        "relevance": 0.5,
    }


@pytest.mark.asyncio
async def test_substring_fallback_merges_and_dedupes():
    """BM25 hits keep priority; substring hits are appended without dupes."""
    bm25 = [_bm25_result("source:a", 8.0), _bm25_result("source:b", 6.0)]
    substring = [
        _substring_result("source:b"),  # duplicate - must be skipped
        _substring_result("source:c"),
        _substring_result("source:d"),
    ]

    async def fake_repo_query(sql, params):
        if "fn::text_search" in sql:
            return bm25
        return substring

    with patch(
        "open_notebook.domain.notebook.repo_query", new=fake_repo_query
    ):
        results = await text_search("中海油冲洗剂", 30)

    assert [r["id"] for r in results] == [
        "source:a",
        "source:b",
        "source:c",
        "source:d",
    ]
    assert results[0]["relevance"] == 8.0
    assert results[3]["relevance"] == 0.5


@pytest.mark.asyncio
async def test_substring_fallback_respects_source_and_note_flags():
    """source=False skips source/insight scans; note=False skips note scans."""
    calls: list[str] = []

    async def fake_repo_query(sql, params):
        calls.append(sql)
        if "fn::text_search" in sql:
            return []
        return []

    with patch(
        "open_notebook.domain.notebook.repo_query", new=fake_repo_query
    ):
        await text_search("kw", 10, source=True, note=False)
        assert len(calls) == 3  # bm25 + source + insight
        await text_search("kw", 10, source=False, note=True)
        assert len(calls) == 5  # + bm25 + note
        await text_search("kw", 10, source=False, note=False)
        assert len(calls) == 6  # + bm25 only


@pytest.mark.asyncio
async def test_whitespace_keyword_skips_substring_fallback():
    """A whitespace-only keyword must not run substring scans (contains '')."""
    calls: list[str] = []

    async def fake_repo_query(sql, params):
        calls.append(sql)
        return []

    with patch(
        "open_notebook.domain.notebook.repo_query", new=fake_repo_query
    ):
        await text_search("   ", 10)
        assert len(calls) == 1  # bm25 only
        assert "fn::text_search" in calls[0]


@pytest.mark.asyncio
async def test_results_are_truncated_to_limit():
    """The merged list is truncated to the requested result count."""
    bm25 = [_bm25_result(f"source:{i}", 5.0) for i in range(5)]
    substring = [_substring_result(f"note:{i}") for i in range(10)]

    async def fake_repo_query(sql, params):
        if "fn::text_search" in sql:
            return bm25
        return substring

    with patch(
        "open_notebook.domain.notebook.repo_query", new=fake_repo_query
    ):
        results = await text_search("kw", 8)

    assert len(results) == 8
