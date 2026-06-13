"""Tests for Tavily web-search timeout behavior."""

import asyncio
import types

import pytest


class FakeSettings:
    tavily_api_key = "test-key"
    tavily_include_domains = "example.com"


class SlowTavilySearchResults:
    def __init__(self, *args, **kwargs):
        pass

    async def ainvoke(self, payload):
        await asyncio.sleep(0.05)
        return [{"title": "Late", "url": "https://example.com", "content": "late result"}]


class CountingTavilySearchResults:
    call_count = 0

    def __init__(self, *args, **kwargs):
        pass

    async def ainvoke(self, payload):
        self.__class__.call_count += 1
        return [{"title": "Result", "url": "https://example.com", "content": payload["query"]}]


@pytest.mark.asyncio
async def test_tavily_search_returns_timeout_message(monkeypatch):
    from open_notebook.domain import content_settings
    from open_notebook.graphs import tools

    async def get_settings():
        return FakeSettings()

    monkeypatch.setenv("TAVILY_SEARCH_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setattr(content_settings.ContentSettings, "get_instance", get_settings)

    tavily_module = __import__(
        "langchain_community.tools.tavily_search",
        fromlist=["TavilySearchResults"],
    )
    utilities_module = __import__(
        "langchain_community.utilities.tavily_search",
        fromlist=["TavilySearchAPIWrapper"],
    )
    monkeypatch.setattr(tavily_module, "TavilySearchResults", SlowTavilySearchResults)
    monkeypatch.setattr(
        utilities_module,
        "TavilySearchAPIWrapper",
        lambda **kwargs: types.SimpleNamespace(**kwargs),
    )

    result = await tools.tavily_search.ainvoke({"query": "slow query"})

    assert "timed out" in result.lower()


@pytest.mark.asyncio
async def test_tavily_search_limits_calls_per_chat_trace(monkeypatch):
    from open_notebook.domain import content_settings
    from open_notebook.graphs import tools
    from open_notebook.graphs.observability import chat_trace_id

    async def get_settings():
        return FakeSettings()

    CountingTavilySearchResults.call_count = 0
    monkeypatch.setenv("TAVILY_SEARCH_MAX_CALLS", "1")
    monkeypatch.setattr(content_settings.ContentSettings, "get_instance", get_settings)

    tavily_module = __import__(
        "langchain_community.tools.tavily_search",
        fromlist=["TavilySearchResults"],
    )
    utilities_module = __import__(
        "langchain_community.utilities.tavily_search",
        fromlist=["TavilySearchAPIWrapper"],
    )
    monkeypatch.setattr(tavily_module, "TavilySearchResults", CountingTavilySearchResults)
    monkeypatch.setattr(
        utilities_module,
        "TavilySearchAPIWrapper",
        lambda **kwargs: types.SimpleNamespace(**kwargs),
    )

    token = chat_trace_id.set("trace-limit-test")
    try:
        first_result = await tools.tavily_search.ainvoke({"query": "first query"})
        second_result = await tools.tavily_search.ainvoke({"query": "second query"})
    finally:
        chat_trace_id.reset(token)
        tools.reset_tavily_trace_state("trace-limit-test")

    assert "first query" in first_result
    assert "maximum web search calls" in second_result.lower()
    assert CountingTavilySearchResults.call_count == 1
