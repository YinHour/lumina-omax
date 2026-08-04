"""Tests for notebook guide / follow-up question JSON parsing robustness."""

import pytest

from api.notebook_guide_service import (
    _extract_questions_fallback,
    parse_guide_json,
)


class TestParseGuideJson:
    def test_clean_json(self):
        raw = '{"summary": "摘要", "questions": ["问1", "问2", "问3"]}'
        summary, questions = parse_guide_json(raw)
        assert summary == "摘要"
        assert questions == ["问1", "问2", "问3"]

    def test_json_wrapped_in_code_fence(self):
        raw = '```json\n{"summary": "摘要", "questions": ["问1", "问2", "问3"]}\n```'
        summary, questions = parse_guide_json(raw)
        assert summary == "摘要"
        assert questions == ["问1", "问2", "问3"]

    def test_prose_before_code_fence(self):
        raw = '好的，以下是导览：\n```json\n{"summary": "摘要", "questions": ["问1", "问2", "问3"]}\n```'
        summary, questions = parse_guide_json(raw)
        assert summary == "摘要"
        assert questions == ["问1", "问2", "问3"]

    def test_truncated_json_is_repaired(self):
        # Missing closing brace/array (max_tokens truncation)
        raw = '{"summary": "摘要", "questions": ["问1", "问2", "问3'
        summary, questions = parse_guide_json(raw)
        assert summary == "摘要"
        assert questions == ["问1", "问2", "问3"]

    def test_truncated_within_questions_array(self):
        raw = '{"summary": "摘要", "questions": ["问1", "问2"'
        summary, questions = parse_guide_json(raw)
        assert summary == "摘要"
        assert questions == ["问1", "问2"]

    def test_unparseable_returns_empty(self):
        summary, questions = parse_guide_json("完全不是 JSON 的内容")
        assert summary is None
        assert questions == []

    def test_unparseable_raises_when_requested(self):
        with pytest.raises(ValueError):
            parse_guide_json("不是 JSON", raise_on_json_error=True)

    def test_questions_salvaged_from_broken_json(self):
        raw = '这里坏了 {"summary": "摘要", "questions": ["问1", "问2", "问3"]'
        summary, questions = parse_guide_json(raw)
        assert summary == "摘要"
        assert questions == ["问1", "问2", "问3"]

    def test_questions_fallback_without_json(self):
        raw = '"questions": ["问1", "问2", "问3"]'
        assert _extract_questions_fallback(raw) == ["问1", "问2", "问3"]

    def test_empty_input(self):
        assert parse_guide_json("") == (None, [])
        assert parse_guide_json(None) == (None, [])

    def test_questions_capped_at_three(self):
        raw = '{"summary": "s", "questions": ["1", "2", "3", "4", "5"]}'
        _, questions = parse_guide_json(raw)
        assert len(questions) == 3

    def test_non_string_questions_ignored(self):
        raw = '{"summary": "s", "questions": ["1", 42, null, {"x": 1}]}'
        _, questions = parse_guide_json(raw)
        assert questions == ["1"]
