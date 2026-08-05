"""Regression: parallel provide_answer updates must merge without InvalidUpdateError.

The Ask graph fans out one provide_answer node per strategy search via Send.
Every node returns "ids"; ThreadState must declare an Annotated reducer for it,
otherwise LangGraph raises INVALID_CONCURRENT_GRAPH_UPDATE when >=2 searches
run in the same superstep.
"""

import json
from types import SimpleNamespace

import pytest

SEARCH_RESULTS = {
    "alpha": [
        {"id": "source_embedding:a1", "parent_id": "source:alpha"},
        {"id": "source_insight:ai1", "parent_id": "source:alpha"},
    ],
    "beta": [
        {"id": "source_embedding:b1", "parent_id": "source:beta"},
    ],
}

STRATEGY_JSON = json.dumps(
    {
        "reasoning": "two independent searches",
        "searches": [
            {"term": "alpha", "instructions": "find alpha evidence"},
            {"term": "beta", "instructions": "find beta evidence"},
        ],
    }
)


class FakeModel:
    def __init__(self, content: str):
        self._content = content

    async def ainvoke(self, *args, **kwargs):
        return SimpleNamespace(content=self._content)


def _fake_model_for_prompt(prompt: str) -> FakeModel:
    if "知识库来源总数" in prompt:
        return FakeModel("FINAL ANSWER TEXT")
    if "# SEARCH STRATEGY" in prompt:
        return FakeModel("partial answer")
    return FakeModel(STRATEGY_JSON)


@pytest.mark.asyncio
async def test_parallel_searches_merge_ids_without_invalid_update(monkeypatch):
    from open_notebook.graphs import ask

    async def fake_provision(prompt, *args, **kwargs):
        return _fake_model_for_prompt(prompt)

    async def fake_vector_search(term, *args, **kwargs):
        return [dict(r) for r in SEARCH_RESULTS.get(term, [])]

    async def fake_graph_search(*args, **kwargs):
        return []

    monkeypatch.setattr(ask, "provision_langchain_model", fake_provision)
    monkeypatch.setattr(ask, "vector_search", fake_vector_search)
    monkeypatch.setattr(ask, "graph_search", fake_graph_search)
    monkeypatch.setenv("ENABLE_KNOWLEDGE_GRAPH", "false")

    result = await ask.graph.ainvoke(
        {
            "question": "compare alpha and beta",
            "corpus_stats": {"total_sources": 2, "embedded_sources": 2},
        }
    )

    assert len(result["answers"]) == 2
    assert sorted(result["ids"]) == sorted(
        ["source_embedding:a1", "source_insight:ai1", "source_embedding:b1"]
    )
    assert set(result["retrieved_source_ids"]) == {"source:alpha", "source:beta"}
    assert result["final_answer"] == "FINAL ANSWER TEXT"


@pytest.mark.asyncio
async def test_single_search_still_returns_ids(monkeypatch):
    from open_notebook.graphs import ask

    single = json.dumps(
        {
            "reasoning": "one search",
            "searches": [{"term": "alpha", "instructions": "find alpha evidence"}],
        }
    )

    async def fake_provision(prompt, *args, **kwargs):
        if "知识库来源总数" in prompt:
            return FakeModel("FINAL")
        if "# SEARCH STRATEGY" in prompt:
            return FakeModel("partial answer")
        return FakeModel(single)

    async def fake_vector_search(term, *args, **kwargs):
        return [dict(r) for r in SEARCH_RESULTS.get(term, [])]

    monkeypatch.setattr(ask, "provision_langchain_model", fake_provision)
    monkeypatch.setattr(ask, "vector_search", fake_vector_search)
    monkeypatch.setattr(ask, "graph_search", lambda *a, **k: _awaitable([]))
    monkeypatch.setenv("ENABLE_KNOWLEDGE_GRAPH", "false")

    result = await ask.graph.ainvoke(
        {
            "question": "alpha only",
            "corpus_stats": {"total_sources": 1, "embedded_sources": 1},
        }
    )

    assert result["ids"] == ["source_embedding:a1", "source_insight:ai1"]
    assert result["final_answer"] == "FINAL"


async def _awaitable(value):
    return value
