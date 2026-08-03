"""Tests for repo_query multi-statement result handling.

The surrealdb client's ``query()`` only returns the first statement's result,
silently dropping data from ``LET ...; RETURN ...`` queries. ``repo_query``
parses the raw response instead and returns the last statement's result.
"""

from unittest.mock import AsyncMock, patch

import pytest

from open_notebook.database.repository import (
    _extract_query_results,
    repo_query,
)


class TestExtractQueryResults:
    """Pure parsing of raw SurrealDB query responses."""

    def test_single_statement_passthrough(self):
        response = {
            "id": "x",
            "result": [{"result": [{"a": 1}], "status": "OK"}],
        }
        assert _extract_query_results(response) == [{"a": 1}]

    def test_multi_statement_returns_last_result(self):
        response = {
            "id": "x",
            "result": [
                {"result": None, "status": "OK"},
                {"result": 3, "status": "OK"},
            ],
        }
        assert _extract_query_results(response) == 3

    def test_let_then_return_select(self):
        response = {
            "id": "x",
            "result": [
                {"result": None, "status": "OK"},
                {"result": None, "status": "OK"},
                {"result": None, "status": "OK"},
                {"result": [{"id": "source:abc"}], "status": "OK"},
            ],
        }
        assert _extract_query_results(response) == [{"id": "source:abc"}]

    def test_last_statement_none_result(self):
        response = {
            "id": "x",
            "result": [
                {"result": None, "status": "OK"},
                {"result": None, "status": "OK"},
            ],
        }
        assert _extract_query_results(response) is None

    def test_statement_error_raises_runtime_error(self):
        response = {
            "id": "x",
            "result": [
                {"result": None, "status": "OK"},
                {"result": None, "status": "ERR", "detail": "boom happened"},
            ],
        }
        with pytest.raises(RuntimeError, match="boom happened"):
            _extract_query_results(response)

    def test_response_level_error_raises_runtime_error(self):
        response = {
            "id": "x",
            "error": {"code": -32000, "message": "Parse error near token"},
        }
        with pytest.raises(RuntimeError, match="Parse error near token"):
            _extract_query_results(response)

    def test_non_dict_passthrough(self):
        assert _extract_query_results(None) is None
        assert _extract_query_results([1, 2]) == [1, 2]


class TestRepoQueryUsesQueryRaw:
    """repo_query must use query_raw and surface the last statement."""

    @pytest.mark.asyncio
    async def test_returns_last_statement_result(self):
        raw_response = {
            "id": "x",
            "result": [
                {"result": None, "status": "OK"},
                {"result": [{"id": "source:abc"}], "status": "OK"},
            ],
        }
        conn = AsyncMock()
        conn.query_raw = AsyncMock(return_value=raw_response)

        with patch("open_notebook.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await repo_query("LET $x = 1; RETURN SELECT * FROM source;")

        conn.query_raw.assert_awaited_once_with(
            "LET $x = 1; RETURN SELECT * FROM source;", None
        )
        assert result == [{"id": "source:abc"}]

    @pytest.mark.asyncio
    async def test_statement_error_propagates(self):
        raw_response = {
            "id": "x",
            "result": [
                {"result": None, "status": "ERR", "detail": "conflict"},
            ],
        }
        conn = AsyncMock()
        conn.query_raw = AsyncMock(return_value=raw_response)

        with patch("open_notebook.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RuntimeError, match="conflict"):
                await repo_query("RETURN 1;")
