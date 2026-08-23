"""Tests for the embedding restore hook (egress-redaction gateway)."""

import pytest

import open_notebook.ai.redaction_gateway as gateway_module
from open_notebook.utils.embedding import _restore_for_embedding


class FakeRestoreService:
    def __init__(self, mapping=None, fail=False):
        self.mapping = mapping or {}
        self.fail = fail
        self.calls = []

    async def restore_text(self, text):
        self.calls.append(text)
        if self.fail:
            raise RuntimeError("gateway down")
        return self.mapping.get(text, text)


class TestRestoreForEmbedding:
    @pytest.mark.asyncio
    async def test_alias_queries_restored(self, monkeypatch):
        service = FakeRestoreService(mapping={"工程师A的实验": "张三的实验"})
        monkeypatch.setattr(gateway_module, "redaction_service", service)
        out = await _restore_for_embedding(["工程师A的实验", "普通文本"])
        assert out == ["张三的实验", "普通文本"]
        assert service.calls == ["工程师A的实验", "普通文本"]

    @pytest.mark.asyncio
    async def test_original_text_noop(self, monkeypatch):
        service = FakeRestoreService()
        monkeypatch.setattr(gateway_module, "redaction_service", service)
        out = await _restore_for_embedding(["张三的实验"])
        assert out == ["张三的实验"]

    @pytest.mark.asyncio
    async def test_gateway_failure_passes_through(self, monkeypatch):
        service = FakeRestoreService(fail=True)
        monkeypatch.setattr(gateway_module, "redaction_service", service)
        out = await _restore_for_embedding(["工程师A的实验"])
        assert out == ["工程师A的实验"]

    @pytest.mark.asyncio
    async def test_empty_list(self):
        assert await _restore_for_embedding([]) == []
