import ast
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_check_duplicate_filenames_matches_case_insensitively(monkeypatch):
    from api.routers import sources

    async def fake_repo_query(query, params=None):
        assert params == {"normalized_filenames": ["experiment.xls", "report.doc"]}
        assert "NULL" not in query.upper()
        assert "asset.original_filename != none" in query
        assert (
            "string::lowercase(string::trim(asset.original_filename)) IN "
            "$normalized_filenames"
        ) in query
        return ["Experiment.XLS", " REPORT.DOC "]

    monkeypatch.setattr(sources, "repo_query", fake_repo_query)

    result = await sources.check_duplicate_filenames([" experiment.xls ", "report.doc"])

    assert result == {"duplicates": [" experiment.xls ", "report.doc"]}


@pytest.mark.asyncio
async def test_check_duplicate_filenames_skips_empty_inputs_without_query(monkeypatch):
    from api.routers import sources

    async def fail_repo_query(query, params=None):
        raise AssertionError("repo_query should not be called")

    monkeypatch.setattr(sources, "repo_query", fail_repo_query)

    result = await sources.check_duplicate_filenames(["", "   ", None])

    assert result == {"duplicates": []}


def test_source_asset_responses_include_original_filename():
    source_path = Path(__file__).resolve().parents[1] / "api" / "routers" / "sources.py"
    tree = ast.parse(source_path.read_text())
    asset_model_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AssetModel"
    ]

    assert asset_model_calls
    missing_lines = [
        node.lineno
        for node in asset_model_calls
        if "original_filename" not in {keyword.arg for keyword in node.keywords}
    ]

    assert missing_lines == []
