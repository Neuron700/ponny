from __future__ import annotations

from datetime import date

import pytest

from pennypilot import db
from pennypilot.models import CategoryRule
from pennypilot.services import csv_import
from pennypilot.services.csv_import import (
    ColumnMapping,
    CsvImportError,
    ImportOptions,
    analyze_import,
    import_rows,
    load_demo_data,
    read_csv_file,
)
from pennypilot.utils import DomainError, make_fingerprint, parse_amount, parse_transaction_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234.567,89", 1_234_567.89),
        ("1,234,567.89", 1_234_567.89),
        ("Rp 1.234", 1234.0),
        ("(25.000)", -25_000.0),
        ("-12500", -12_500.0),
        ("1,5", 1.5),
        ("2.500", 2500.0),
        ("1234.56", 1234.56),
    ],
)
def test_parse_amount_variants(raw, expected):
    assert parse_amount(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "abc", "Rp", "--"])
def test_parse_amount_invalid(raw):
    with pytest.raises(DomainError):
        parse_amount(raw)


def test_parse_date_iso_and_explicit_format():
    assert parse_transaction_date("2026-03-04") == date(2026, 3, 4)
    assert parse_transaction_date("04/03/2026", "%d/%m/%Y") == date(2026, 3, 4)
    assert parse_transaction_date("04/03/2026") == date(2026, 3, 4)
    with pytest.raises(DomainError):
        parse_transaction_date("31/02/2026")


def _base_csv(rows: str) -> bytes:
    return (
        "tanggal,deskripsi,nominal,tipe,kategori\n" + rows
    ).encode("utf-8")


def _analyze(
    data: bytes,
    *,
    mode: str = "signed",
    date_format: str | None = "%Y-%m-%d",
    existing: set[str] | None = None,
    rules: list[CategoryRule] | None = None,
):
    loaded = read_csv_file(data)
    mapping = ColumnMapping("tanggal", "deskripsi", "nominal", "tipe", "kategori")
    analysis = analyze_import(
        loaded.frame,
        mapping,
        ImportOptions(amount_mode=mode, date_format=date_format),
        existing_fingerprints=existing or set(),
        rules=rules or [],
        source_file="test.csv",
        encoding=loaded.encoding,
        delimiter=loaded.delimiter,
        parse_issues=loaded.parse_issues,
        total_rows=loaded.total_rows,
    )
    return loaded, analysis


def test_read_csv_detects_semicolon():
    data = b"tanggal;deskripsi;nominal\n2026-01-01;Kopi;-20000\n"
    loaded = read_csv_file(data)
    assert loaded.delimiter == ";"
    assert loaded.frame.shape == (1, 3)
    assert loaded.frame.index.tolist() == [2]


def test_invalid_rows_are_reported_without_failing_file():
    data = _base_csv(
        "2026-01-01,Kopi,-20000,expense,\n"
        "bukan-tanggal,Teh,-10000,expense,\n"
        ",Roti,-15000,expense,\n"
        "2026-01-02,,abc,expense,\n"
        "2026-01-03,Valid,-30000,expense,\n"
    )
    _, analysis = _analyze(data)
    assert analysis.total_rows == 5
    assert analysis.valid_count == 2
    assert analysis.invalid_row_count == 3
    reasons = " ".join(issue.message for issue in analysis.issues)
    assert "Tanggal" in reasons
    assert "Deskripsi kosong" in reasons
    assert "Nominal" in reasons


def test_malformed_column_count_is_reported():
    data = b"tanggal,deskripsi,nominal\n2026-01-01,Kopi,-20000,extra\n2026-01-02,Teh,-10000\n"
    loaded = read_csv_file(data)
    assert len(loaded.parse_issues) == 1
    assert "Jumlah kolom" in loaded.parse_issues[0].message
    mapping = ColumnMapping("tanggal", "deskripsi", "nominal")
    analysis = analyze_import(
        loaded.frame,
        mapping,
        ImportOptions(date_format="%Y-%m-%d"),
        parse_issues=loaded.parse_issues,
        total_rows=loaded.total_rows,
    )
    assert analysis.valid_count == 1
    assert analysis.invalid_row_count == 1


def test_signed_mode_uses_sign():
    _, analysis = _analyze(
        _base_csv(
            "2026-01-01,Gaji,5000000,income,\n"
            "2026-01-02,Kopi,-25000,expense,\n"
        )
    )
    types = {row.transaction.description: row.transaction.transaction_type for row in analysis.rows}
    assert types["Gaji"] == "income"
    assert types["Kopi"] == "expense"
    assert all(row.transaction.amount >= 0 for row in analysis.rows)


def test_absolute_with_type_mode():
    _, analysis = _analyze(
        _base_csv(
            "2026-01-01,Gaji,5000000,pemasukan,\n"
            "2026-01-02,Kopi,25000,pengeluaran,\n"
        ),
        mode="absolute_with_type",
    )
    assert analysis.valid_count == 2
    by_desc = {row.transaction.description: row.transaction.transaction_type for row in analysis.rows}
    assert by_desc == {"Gaji": "income", "Kopi": "expense"}


def test_absolute_mode_requires_type_column():
    data = b"tanggal,deskripsi,nominal\n2026-01-01,Kopi,25000\n"
    loaded = read_csv_file(data)
    with pytest.raises(CsvImportError, match="kolom tipe"):
        analyze_import(
            loaded.frame,
            ColumnMapping("tanggal", "deskripsi", "nominal"),
            ImportOptions(amount_mode="absolute_with_type", date_format="%Y-%m-%d"),
        )


def test_all_expense_mode_and_zero_amount():
    _, analysis = _analyze(
        _base_csv(
            "2026-01-01,Kopi,25000,expense,\n"
            "2026-01-02,Teh,-15000,expense,\n"
            "2026-01-03,Gula,0,expense,\n"
        ),
        mode="all_expense",
    )
    assert analysis.valid_count == 2
    assert all(row.transaction.transaction_type == "expense" for row in analysis.rows)
    assert [row.transaction.amount for row in analysis.rows] == [25000.0, 15000.0]
    assert analysis.invalid_row_count == 1


def test_absolute_with_type_rejects_zero_amount():
    _, analysis = _analyze(
        _base_csv("2026-01-01,Kopi,0,pengeluaran,\n"),
        mode="absolute_with_type",
    )
    assert analysis.valid_count == 0
    assert analysis.invalid_row_count == 1
    assert "nol" in analysis.issues[0].message


def test_unknown_type_value_is_invalid():
    _, analysis = _analyze(
        _base_csv("2026-01-01,Kopi,25000,aneh,\n"),
        mode="absolute_with_type",
    )
    assert analysis.valid_count == 0
    assert "Tipe" in analysis.issues[0].message


def test_csv_category_is_preserved_and_unknown_category_falls_back():
    rules = [CategoryRule(1, "kopi", "Makanan")]
    _, analysis = _analyze(
        _base_csv(
            "2026-01-01,Kopi,25000,expense,hiburan\n"
            "2026-01-02,Kopi,25000,expense,Kategori Tidak Ada\n",
        ),
        rules=rules,
    )
    assert analysis.rows[0].transaction.category == "Hiburan"
    assert analysis.rows[0].transaction.category_source == "csv"
    assert analysis.rows[1].transaction.category == "Makanan"
    assert analysis.rows[1].transaction.category_source == "rule"
    assert any("tidak dikenal" in warning for warning in analysis.warnings)


def test_duplicate_within_file_and_existing_database():
    data = _base_csv(
        "2026-01-01,Kopi,-25000,expense,\n"
        "2026-01-01,Kopi,-25000,expense,\n"
        "2026-01-02,Teh,-10000,expense,\n"
    )
    existing = {make_fingerprint(date(2026, 1, 2), "Teh", 10_000, "expense")}
    _, analysis = _analyze(data, existing=existing)
    assert analysis.duplicate_count == 2
    assert analysis.ready_count == 1
    assert "baris 2" in analysis.rows[1].duplicate_reason
    assert "database" in analysis.rows[2].duplicate_reason


def test_ambiguous_date_format_is_flagged():
    data = _base_csv("01/02/2026,Kopi,-25000,expense,\n")
    _, auto = _analyze(data, date_format=None)
    assert auto.ambiguous_dates is True
    assert any("ambigu" in warning for warning in auto.warnings)
    _, explicit = _analyze(data, date_format="%d/%m/%Y")
    assert explicit.ambiguous_dates is False
    assert explicit.rows[0].transaction.transaction_date == date(2026, 2, 1)


@pytest.mark.parametrize(
    ("raw_date", "explicit_format", "expected"),
    [
        ("01-02-2026", "%m-%d-%Y", date(2026, 1, 2)),
        ("01.02.2026", "%m.%d.%Y", date(2026, 1, 2)),
    ],
)
def test_hyphen_and_dot_date_ambiguity_is_flagged(raw_date, explicit_format, expected):
    data = _base_csv(f"{raw_date},Kopi,-25000,expense,\n")
    _, auto = _analyze(data, date_format=None)
    assert auto.ambiguous_dates is True
    _, explicit = _analyze(data, date_format=explicit_format)
    assert explicit.ambiguous_dates is False
    assert explicit.rows[0].transaction.transaction_date == expected


def test_import_rows_skips_duplicates_then_can_include_them(connection):
    data = _base_csv(
        "2026-01-01,Kopi,-25000,expense,\n"
        "2026-01-01,Kopi,-25000,expense,\n"
        "2026-01-02,Teh,-10000,expense,\n"
    )
    _, analysis = _analyze(data)
    assert import_rows(connection, analysis) == 2
    assert db.count_transactions(connection) == 2

    _, second = _analyze(data, existing=db.get_existing_fingerprints(connection))
    assert second.duplicate_count == 3
    assert import_rows(connection, second) == 0
    assert import_rows(connection, second, include_duplicates=True) == 3
    assert db.count_transactions(connection) == 5


def test_import_second_file_reports_existing(connection):
    first = _base_csv("2026-01-01,Kopi,-25000,expense,\n")
    _, analysis = _analyze(first)
    import_rows(connection, analysis)
    _, repeated = _analyze(first, existing=db.get_existing_fingerprints(connection))
    assert repeated.duplicate_count == 1
    assert repeated.rows[0].duplicate_reason == "Sudah ada di database."


def test_file_size_limit(monkeypatch):
    monkeypatch.setattr(csv_import, "MAX_FILE_SIZE_BYTES", 10)
    with pytest.raises(CsvImportError, match="melebihi batas"):
        read_csv_file(b"tanggal,deskripsi,nominal\n2026-01-01,Kopi,1000\n")


def test_row_limit(monkeypatch):
    monkeypatch.setattr(csv_import, "MAX_IMPORT_ROWS", 1)
    data = _base_csv("2026-01-01,Kopi,-1000,expense,\n2026-01-02,Teh,-1000,expense,\n")
    with pytest.raises(CsvImportError, match="baris"):
        read_csv_file(data)


def test_cp1252_encoding():
    data = "tanggal,deskripsi,nominal\n2026-01-01,Café,-10000\n".encode("cp1252")
    loaded = read_csv_file(data, encoding="cp1252")
    assert loaded.frame.iloc[0]["deskripsi"] == "Café"


def test_demo_dataset_loads(connection):
    analysis, imported = load_demo_data(connection)
    assert analysis.invalid_row_count == 0
    assert imported > 150
    assert db.count_transactions(connection) == imported
    months = db.get_available_months(connection)
    assert "2026-09" in months
