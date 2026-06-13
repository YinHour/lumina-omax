"""Tests for chat observability helpers."""


def test_log_chat_info_emits_trace_step_and_fields(monkeypatch):
    from api.routers import chat

    messages: list[str] = []
    monkeypatch.setattr(chat.logger, "info", messages.append)

    chat.log_chat_info(
        "trace-1",
        "request_start",
        session_id="chat_session:abc",
        enable_web_search=True,
        context_tokens=123,
    )

    assert messages == [
        "chat_trace=trace-1 step=request_start "
        "session_id=chat_session:abc enable_web_search=True context_tokens=123"
    ]


def test_estimate_context_stats_counts_context_text(monkeypatch):
    from api.routers import chat

    monkeypatch.setattr(chat, "token_count", lambda text: len(text.split()))

    stats = chat.estimate_context_stats({"sources": [{"content": "one two"}], "notes": []})

    assert stats["context_chars"] > 0
    assert stats["context_tokens"] > 0
