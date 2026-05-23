from open_notebook.utils.office_converter import convert_to_modern_office_format


def test_spreadsheets_are_not_converted_to_pdf(tmp_path):
    xlsx_file = tmp_path / "experiment.xlsx"
    xls_file = tmp_path / "legacy_experiment.xls"
    xlsx_file.write_bytes(b"placeholder")
    xls_file.write_bytes(b"placeholder")

    assert convert_to_modern_office_format(str(xlsx_file)) == str(xlsx_file)
    assert convert_to_modern_office_format(str(xls_file)) == str(xls_file)
