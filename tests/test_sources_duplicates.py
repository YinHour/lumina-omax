import pytest


@pytest.mark.asyncio
async def test_check_duplicate_filenames_matches_case_insensitively(monkeypatch):
    from api.routers import sources

    async def fake_repo_query(query, params=None):
        assert params is None
        assert "NULL" not in query.upper()
        assert "asset.original_filename != none" in query
        return ["Experiment.XLS", " REPORT.DOC "]

    monkeypatch.setattr(sources, "repo_query", fake_repo_query)

    result = await sources.check_duplicate_filenames([" experiment.xls ", "report.doc"])

    assert result == {"duplicates": [" experiment.xls ", "report.doc"]}
