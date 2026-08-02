import subprocess

import pytest

from open_notebook.utils.office_converter import convert_to_modern_office_format


def test_modern_spreadsheets_are_not_converted_to_pdf(tmp_path):
    xlsx_file = tmp_path / "experiment.xlsx"
    xlsx_file.write_bytes(b"placeholder")

    assert convert_to_modern_office_format(str(xlsx_file)) == str(xlsx_file)


def test_legacy_xls_is_converted_to_xlsx_via_subprocess(tmp_path, monkeypatch):
    xls_file = tmp_path / "legacy_experiment.xls"
    xls_file.write_bytes(b"placeholder")
    converted_file = tmp_path / "legacy_experiment.xlsx"

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        converted_file.write_bytes(b"converted")

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(
        "open_notebook.utils.office_converter.subprocess.run",
        fake_run,
        raising=False,
    )

    result = convert_to_modern_office_format(str(xls_file))

    assert result == str(converted_file)
    assert calls
    assert "xlsx" in calls[0]


@pytest.mark.parametrize("ext", ["doc", "docx", "ppt", "pptx"])
def test_documents_and_presentations_are_converted_via_subprocess(
    tmp_path, monkeypatch, ext
):
    """Non-spreadsheet Office files should be sent through the conversion path.

    We monkeypatch subprocess.run inside office_converter so the test does not
    depend on LibreOffice actually being installed.
    """
    input_file = tmp_path / f"experiment.{ext}"
    input_file.write_bytes(b"placeholder")

    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(
        "open_notebook.utils.office_converter.subprocess.run",
        fake_run,
        raising=False,
    )

    result = convert_to_modern_office_format(str(input_file))

    assert calls["count"] >= 1
    assert isinstance(result, str)
    assert result


@pytest.mark.parametrize("ext", ["txt", "pdf"])
def test_non_office_files_are_returned_unchanged_no_conversion(
    tmp_path, monkeypatch, ext
):
    """Non-Office files should follow the early-return path and not be converted."""
    input_file = tmp_path / f"notes.{ext}"
    input_file.write_bytes(b"placeholder")

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "subprocess.run should not be called for non-Office files"
        )

    monkeypatch.setattr(
        "open_notebook.utils.office_converter.subprocess.run",
        fail_if_called,
        raising=False,
    )

    result = convert_to_modern_office_format(str(input_file))
    assert result == str(input_file)


def test_extension_case_and_multiple_dots_handled_correctly(tmp_path, monkeypatch):
    """Extension parsing should be case-insensitive and handle multiple dots."""
    # Uppercase modern spreadsheet extension: should *not* be converted
    xlsx_upper = tmp_path / "EXPERIMENT.XLSX"
    xlsx_upper.write_bytes(b"placeholder")

    # Document with multiple dots in the filename: should be converted
    doc_with_dots = tmp_path / "report.final.DOCX"
    doc_with_dots.write_bytes(b"placeholder")

    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(
        "open_notebook.utils.office_converter.subprocess.run",
        fake_run,
        raising=False,
    )

    xlsx_result = convert_to_modern_office_format(str(xlsx_upper))
    assert xlsx_result == str(xlsx_upper)

    doc_result = convert_to_modern_office_format(str(doc_with_dots))
    assert isinstance(doc_result, str)
    assert calls["count"] >= 1


def test_missing_libreoffice_logs_actionable_error_and_falls_back(
    tmp_path, monkeypatch, caplog
):
    """A missing LibreOffice binary must not crash and must log an actionable message."""
    doc_file = tmp_path / "experiment.doc"
    doc_file.write_bytes(b"placeholder")

    monkeypatch.setattr(
        "open_notebook.utils.office_converter.get_libreoffice_command",
        lambda: "/nonexistent/soffice",
    )

    result = convert_to_modern_office_format(str(doc_file))

    assert result == str(doc_file)
    assert any("LibreOffice executable not found" in r.message for r in caplog.records)
    assert any("brew install --cask libreoffice" in r.message for r in caplog.records)


def test_libreoffice_failure_logs_exit_code_and_falls_back(
    tmp_path, monkeypatch, caplog
):
    """A failing LibreOffice run must log exit code/stderr and fall back to the original path."""
    doc_file = tmp_path / "experiment.doc"
    doc_file.write_bytes(b"placeholder")

    monkeypatch.setattr(
        "open_notebook.utils.office_converter.get_libreoffice_command",
        lambda: "/bin/ls",
    )

    class FakeResult:
        returncode = 1
        stderr = b"soffice: cannot open"

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "soffice", output=None, stderr=b"soffice: cannot open")

    monkeypatch.setattr(
        "open_notebook.utils.office_converter.subprocess.run",
        fake_run,
        raising=False,
    )

    result = convert_to_modern_office_format(str(doc_file))

    assert result == str(doc_file)
    assert any("exit code 1" in r.message for r in caplog.records)
    assert any("soffice: cannot open" in r.message for r in caplog.records)


def test_libreoffice_success_but_missing_output_logs_warning(
    tmp_path, monkeypatch, caplog
):
    """A successful exit code without output file must log a clear reason."""
    doc_file = tmp_path / "experiment.doc"
    doc_file.write_bytes(b"placeholder")

    monkeypatch.setattr(
        "open_notebook.utils.office_converter.get_libreoffice_command",
        lambda: "/bin/ls",
    )

    def fake_run(*args, **kwargs):
        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(
        "open_notebook.utils.office_converter.subprocess.run",
        fake_run,
        raising=False,
    )

    result = convert_to_modern_office_format(str(doc_file))

    assert result == str(doc_file)
    assert any(
        "output was not created" in r.message for r in caplog.records
    )
