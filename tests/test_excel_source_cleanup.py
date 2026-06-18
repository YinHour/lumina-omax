from open_notebook.graphs.source import (
    _sanitize_excel_table_newlines,
    _trim_excel_empty_table_rows,
)


def test_excel_cleanup_removes_blank_columns_after_newline_repair():
    markdown = "\n".join(
        [
            "| 产品代号 |  | 温度 |  | 结果 |",
            "| --- | --- | --- | --- | --- |",
            "| A-1 |  | 90C |  | 合格 |",
            "| A-2 |  | 120C |  | 复测 |",
        ]
    )

    cleaned = _trim_excel_empty_table_rows(_sanitize_excel_table_newlines(markdown))

    assert cleaned == "\n".join(
        [
            "| 产品代号 | 温度 | 结果 |",
            "| --- | --- | --- |",
            "| A-1 | 90C | 合格 |",
            "| A-2 | 120C | 复测 |",
        ]
    )


def test_excel_cleanup_keeps_columns_with_any_value():
    markdown = "\n".join(
        [
            "| 产品代号 | 备注 | 结果 |",
            "| --- | --- | --- |",
            "| A-1 |  | 合格 |",
            "| A-2 | 复测 | 通过 |",
        ]
    )

    cleaned = _trim_excel_empty_table_rows(_sanitize_excel_table_newlines(markdown))

    assert cleaned == markdown


def test_excel_cleanup_removes_fully_empty_table():
    markdown = "\n".join(
        [
            "|  |  |",
            "| --- | --- |",
            "|  |  |",
        ]
    )

    cleaned = _trim_excel_empty_table_rows(_sanitize_excel_table_newlines(markdown))

    assert cleaned == ""


def test_excel_cleanup_preserves_text_around_trimmed_table():
    markdown = "\n".join(
        [
            "前置说明",
            "",
            "| 产品代号 |  | 结果 |",
            "| --- | --- | --- |",
            "| A-1 |  | 合格 |",
            "",
            "后续说明",
        ]
    )

    cleaned = _trim_excel_empty_table_rows(_sanitize_excel_table_newlines(markdown))

    assert cleaned == "\n".join(
        [
            "前置说明",
            "",
            "| 产品代号 | 结果 |",
            "| --- | --- |",
            "| A-1 | 合格 |",
            "",
            "后续说明",
        ]
    )
