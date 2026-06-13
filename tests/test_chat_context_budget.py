"""Tests for notebook chat context budgeting."""

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
