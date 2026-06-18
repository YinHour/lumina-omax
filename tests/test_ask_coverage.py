from unittest.mock import AsyncMock

import pytest


def test_source_ids_from_results_normalizes_only_source_parent_ids():
    from open_notebook.graphs.ask import source_ids_from_results

    results = [
        {"id": "source_embedding:1", "parent_id": "source:alpha"},
        {"id": "source_insight:2", "parent_id": {"tb": "source", "id": "beta"}},
        {"id": "note:3", "parent_id": "note:note-one"},
        {"id": "kg_entity:4", "parent_id": "kg_entity:entity-one"},
        {"id": "source_embedding:5", "parent_id": "source:alpha"},
    ]

    assert source_ids_from_results(results) == ["source:alpha", "source:beta"]


def test_format_coverage_summary_reports_total_embedded_and_retrieved_counts():
    from open_notebook.graphs.ask import format_coverage_summary

    summary = format_coverage_summary(
        corpus_stats={"total_sources": 32, "embedded_sources": 31},
        retrieved_source_ids=["source:a", "source:b", "source:a"],
    )

    assert "知识库来源总数：32" in summary
    assert "可检索来源数：31" in summary
    assert "本次检索命中来源数：2" in summary


@pytest.mark.asyncio
async def test_get_ask_corpus_stats_counts_total_and_embedded_sources(monkeypatch):
    from api.routers import search

    repo_query = AsyncMock(side_effect=[[{"count": 32}], [{"count": 31}]])
    monkeypatch.setattr(search, "repo_query", repo_query)

    stats = await search.get_ask_corpus_stats()

    assert stats == {"total_sources": 32, "embedded_sources": 31}
    assert repo_query.await_count == 2
