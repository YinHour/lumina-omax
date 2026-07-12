"""Tests for notebook chat context budgeting and history windowing."""

import importlib

from api.routers.chat import trim_context_data_to_char_budget


def test_trim_context_data_to_char_budget_truncates_large_full_text_sources():
    context_data = {
        "sources": [
            {"id": "source:1", "title": "One", "full_text": "A" * 120},
            {"id": "source:2", "title": "Two", "full_text": "B" * 120},
        ],
        "notes": [],
    }

    original_size = len(str(context_data))

    total_content, was_trimmed = trim_context_data_to_char_budget(context_data, 120)

    assert was_trimmed is True
    assert len(context_data["sources"][0]["full_text"]) < 120
    assert len(context_data["sources"][1]["full_text"]) < 120
    assert "[Content truncated" in context_data["sources"][0]["full_text"]
    assert len(total_content) < original_size


def test_notebook_chat_context_max_chars_default_is_120k(monkeypatch):
    """B-layer: tightened default keeps deepseek-v4-pro room to breathe."""
    monkeypatch.delenv("NOTEBOOK_CHAT_CONTEXT_MAX_CHARS", raising=False)
    import api.routers.chat as chat_module

    reloaded = importlib.reload(chat_module)
    try:
        assert reloaded.NOTEBOOK_CHAT_CONTEXT_MAX_CHARS == 120000
    finally:
        # Re-import to restore module state for other tests.
        importlib.reload(chat_module)


def test_env_positive_int_parses_valid_value(monkeypatch):
    from open_notebook.graphs import chat as chat_graph

    monkeypatch.setenv("CHAT_HISTORY_MAX_MESSAGES_TEST", "20")
    assert chat_graph._env_positive_int("CHAT_HISTORY_MAX_MESSAGES_TEST", 12) == 20


def test_env_positive_int_falls_back_on_invalid(monkeypatch):
    from open_notebook.graphs import chat as chat_graph

    monkeypatch.setenv("CHAT_HISTORY_MAX_MESSAGES_TEST", "abc")
    assert chat_graph._env_positive_int("CHAT_HISTORY_MAX_MESSAGES_TEST", 12) == 12

    monkeypatch.setenv("CHAT_HISTORY_MAX_MESSAGES_TEST", "0")
    assert chat_graph._env_positive_int("CHAT_HISTORY_MAX_MESSAGES_TEST", 12) == 12

    monkeypatch.setenv("CHAT_HISTORY_MAX_MESSAGES_TEST", "-5")
    assert chat_graph._env_positive_int("CHAT_HISTORY_MAX_MESSAGES_TEST", 12) == 12


def test_env_positive_int_uses_default_when_unset(monkeypatch):
    from open_notebook.graphs import chat as chat_graph

    monkeypatch.delenv("CHAT_HISTORY_MAX_MESSAGES_TEST", raising=False)
    assert chat_graph._env_positive_int("CHAT_HISTORY_MAX_MESSAGES_TEST", 12) == 12


def test_quick_and_research_use_shared_protocol_safe_window():
    from open_notebook.graphs import chat as chat_graph
    from open_notebook.graphs import research_agent
    from open_notebook.graphs.message_history import select_history_window

    assert chat_graph.select_history_window is select_history_window
    assert research_agent.select_history_window is select_history_window
