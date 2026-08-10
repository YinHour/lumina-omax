"""Regression: auto-engine path must convert legacy .doc/.ppt to PDF before
content_core extraction.

content_core's auto/simple engine cannot determine the file type of OLE2
binary .doc/.ppt files ("Unable to determine file type"), so the source never
embeds or extracts KG. The fix routes .doc/.ppt through LibreOffice -> PDF in
the non-mineru branch of _sync_extract, mirroring the .xls handling.
"""

import os

import pytest

from open_notebook.graphs import source


class _Sentinel(Exception):
    """Raised by the mocked extract_content to short-circuit downstream
    save/vectorize/KG work so the test only exercises the conversion path."""


def _make_settings():
    from types import SimpleNamespace

    return SimpleNamespace(
        default_content_processing_engine_doc=None,  # content_process resolves to "auto"
        default_content_processing_engine_url=None,
        firecrawl_api_key=None,
    )


async def _noop_get_instance():
    return _make_settings()


class _ModelManagerMock:
    async def get_defaults(self):
        from types import SimpleNamespace

        return SimpleNamespace(default_speech_to_text_model=None)


def _patch_common(monkeypatch, convert_fn, extract_fn):
    """Install the minimal mocking surface for content_process to reach _sync_extract."""
    monkeypatch.setattr(source.ContentSettings, "clear_instance", lambda *a, **k: None)
    monkeypatch.setattr(source.ContentSettings, "get_instance", _noop_get_instance)
    monkeypatch.setattr(source, "ModelManager", _ModelManagerMock)
    monkeypatch.setattr(source, "extract_content", extract_fn)
    import open_notebook.utils.office_converter as oc

    monkeypatch.setattr(oc, "convert_to_modern_office_format", convert_fn)


def _fake_convert_doc_to_pdf(file_path: str) -> str:
    """Simulate LibreOffice producing a PDF beside the source file."""
    return os.path.splitext(file_path)[0] + ".pdf"


@pytest.mark.asyncio
async def test_auto_engine_converts_doc_to_pdf_before_extraction(monkeypatch):
    convert_calls = []
    received = {}

    def convert_fn(file_path):
        convert_calls.append(file_path)
        return _fake_convert_doc_to_pdf(file_path)

    async def extract_fn(state):
        received["file_path"] = state.get("file_path")
        raise _Sentinel("short-circuit after conversion")

    _patch_common(monkeypatch, convert_fn, extract_fn)

    state = {
        "content_state": {
            "file_path": "/tmp/test_report.doc",
            "original_filename": "test_report.doc",
        },
        "source_id": "source:testdoc",
    }

    with pytest.raises(_Sentinel):
        await source.content_process(state)

    assert convert_calls == ["/tmp/test_report.doc"]
    assert received["file_path"] == "/tmp/test_report.pdf"


@pytest.mark.asyncio
async def test_auto_engine_converts_ppt_to_pdf_before_extraction(monkeypatch):
    convert_calls = []
    received = {}

    def convert_fn(file_path):
        convert_calls.append(file_path)
        return os.path.splitext(file_path)[0] + ".pdf"

    async def extract_fn(state):
        received["file_path"] = state.get("file_path")
        raise _Sentinel("short-circuit after conversion")

    _patch_common(monkeypatch, convert_fn, extract_fn)

    state = {
        "content_state": {
            "file_path": "/tmp/deck.ppt",
            "original_filename": "deck.ppt",
        },
        "source_id": "source:testppt",
    }

    with pytest.raises(_Sentinel):
        await source.content_process(state)

    assert convert_calls == ["/tmp/deck.ppt"]
    assert received["file_path"] == "/tmp/deck.pdf"


@pytest.mark.asyncio
async def test_auto_engine_does_not_convert_modern_docx(monkeypatch):
    convert_calls = []
    received = {}

    def convert_fn(file_path):
        convert_calls.append(file_path)
        return file_path

    async def extract_fn(state):
        received["file_path"] = state.get("file_path")
        raise _Sentinel("short-circuit")

    _patch_common(monkeypatch, convert_fn, extract_fn)

    state = {
        "content_state": {
            "file_path": "/tmp/report.docx",
            "original_filename": "report.docx",
        },
        "source_id": "source:testdocx",
    }

    with pytest.raises(_Sentinel):
        await source.content_process(state)

    # .docx is handled natively by content_core; conversion must not run.
    assert convert_calls == []
    assert received["file_path"] == "/tmp/report.docx"
