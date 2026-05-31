"""Unit tests for _sanitize_excel_table_newlines in open_notebook/graphs/source.py."""

import pytest
from open_notebook.graphs.source import _sanitize_excel_table_newlines


class TestSanitizeExcelTableNewlines:
    def test_valid_table_passes_unchanged(self):
        content = (
            "| A | B | C |\n"
            "|---|---|---|\n"
            "| 1 | 2 | 3 |\n"
            "| 4 | 5 | 6 |\n"
        )
        assert _sanitize_excel_table_newlines(content) == content

    def test_broken_multiline_row_merged_with_br(self):
        # content_core may split a long cell into multiple lines
        content = (
            "| Name | Description |\n"
            "|---|---|\n"
            "| Item | Very long description\n"
            "that spans multiple\n"
            "lines in the cell |\n"
        )
        result = _sanitize_excel_table_newlines(content)
        assert "<br>" in result
        assert "Very long description<br>that spans multiple<br>lines in the cell" in result

    def test_non_table_lines_untouched(self):
        content = (
            "# Header\n\n"
            "Plain text paragraph.\n\n"
            "Another line.\n"
        )
        assert _sanitize_excel_table_newlines(content) == content

    def test_markdown_headings_between_tables_not_merged(self):
        content = (
            "| A | B |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
            "## Next Section\n"
            "| X | Y |\n"
            "|---|---|\n"
            "| 3 | 4 |\n"
        )
        result = _sanitize_excel_table_newlines(content)
        assert "## Next Section" in result
        # Tables on either side should still be intact
        assert "| 1 | 2 |" in result
        assert "| 3 | 4 |" in result

    def test_separator_resets_expected_count(self):
        # Each new separator line resets the column count expectation
        content = (
            "| Wide | Column A | Column B |\n"
            "|---|---|---|\n"
            "| Row 1 | data |\n"
            "still row 1 |\n"
            "| Row 2 | ok |\n"
        )
        result = _sanitize_excel_table_newlines(content)
        # First row should have merged parts
        assert "<br>still row 1" in result

    def test_empty_content(self):
        assert _sanitize_excel_table_newlines("") == ""

    def test_single_line_without_pipes(self):
        assert _sanitize_excel_table_newlines("Plain text.") == "Plain text."

    def test_separator_line_variants(self):
        # Separators with alignment colons
        content = (
            "| Name | Value |\n"
            "|:---|---:|\n"
            "| Foo | 42 |\n"
        )
        result = _sanitize_excel_table_newlines(content)
        assert result == content
