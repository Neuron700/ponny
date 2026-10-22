from __future__ import annotations

import csv
import io

from pennypilot.services.exports import transactions_to_csv_bytes


def test_export_is_valid_csv_with_bom_and_readable():
    rows = [
        {
            "id": 1,
            "transaction_date": "2026-01-02",
            "description": "Kopi, susu",
            "transaction_type": "expense",
            "category": "Makanan",
            "category_source": "rule",
            "amount": 25_000,
            "source_file": "contoh.csv",
        }
    ]
    data = transactions_to_csv_bytes(rows)
    assert data.startswith(b"\xef\xbb\xbf")
    decoded = data.decode("utf-8-sig")
    parsed = list(csv.reader(io.StringIO(decoded)))
    assert parsed[0][0] == "ID"
    assert parsed[1][2] == "Kopi, susu"
    assert parsed[1][3] == "Pengeluaran"
    assert parsed[1][6] == "25000.00"


def test_export_sanitizes_spreadsheet_formulas():
    rows = [
        {
            "id": 1,
            "transaction_date": "2026-01-02",
            "description": "=HYPERLINK(\"https://example.com\")",
            "transaction_type": "expense",
            "category": "Makanan",
            "category_source": "manual",
            "amount": 1000,
            "source_file": "@file",
        }
    ]
    decoded = transactions_to_csv_bytes(rows).decode("utf-8-sig")
    parsed = list(csv.reader(io.StringIO(decoded)))
    assert parsed[1][2].startswith("'=")
    assert parsed[1][7].startswith("'@")
