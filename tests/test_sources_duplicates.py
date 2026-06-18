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
