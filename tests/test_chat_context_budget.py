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


def test_select_history_window_keeps_recent_messages():
    from open_notebook.graphs import chat as chat_graph

    messages = [f"m{i}" for i in range(20)]
    trimmed = chat_graph._select_history_window(messages, max_messages=5, trace_id="t")

    assert trimmed == ["m15", "m16", "m17", "m18", "m19"]
    # Source list must be untouched (LangGraph state is the source of truth).
    assert len(messages) == 20


def test_select_history_window_returns_full_list_when_under_cap():
    from open_notebook.graphs import chat as chat_graph

    messages = ["a", "b", "c"]
    trimmed = chat_graph._select_history_window(messages, max_messages=10, trace_id="t")

    assert trimmed == ["a", "b", "c"]
    # Must return a copy, not the same object, so callers can safely prepend.
    assert trimmed is not messages


def test_select_history_window_disabled_when_max_messages_zero():
    from open_notebook.graphs import chat as chat_graph

    messages = [f"m{i}" for i in range(20)]
    trimmed = chat_graph._select_history_window(messages, max_messages=0, trace_id="t")

    assert trimmed == messages


def test_select_history_window_logs_truncation(caplog):
    from loguru import logger

    from open_notebook.graphs import chat as chat_graph

    captured: list[str] = []

    handler_id = logger.add(
        lambda message: captured.append(str(message)),
        level="INFO",
        format="{message}",
    )
    try:
        messages = [f"m{i}" for i in range(30)]
        chat_graph._select_history_window(messages, max_messages=12, trace_id="abc123")
    finally:
        logger.remove(handler_id)

    truncation_logs = [line for line in captured if "step=history_truncated" in line]
    assert truncation_logs, f"expected history_truncated log line in {captured}"
    line = truncation_logs[0]
    assert "chat_trace=abc123" in line
    assert "total_messages=30" in line
    assert "kept_messages=12" in line
    assert "dropped_messages=18" in line
    assert "max_messages=12" in line
