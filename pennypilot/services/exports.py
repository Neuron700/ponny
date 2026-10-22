"""Ekspor transaksi terfilter ke CSV tanpa mengubah data sumber."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from pennypilot.config import SOURCE_LABELS, TYPE_LABELS

EXPORT_COLUMNS = [
    "ID",
    "Tanggal",
    "Deskripsi",
    "Tipe",
    "Kategori",
    "Sumber Kategori",
    "Nominal",
    "File Sumber",
]


def _as_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    raise TypeError("Baris ekspor harus mapping atau sqlite3.Row.")


def _safe_text(value: Any) -> str:
    """Cegah teks CSV dieksekusi sebagai formula saat dibuka di spreadsheet."""

    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def transactions_to_csv_bytes(rows: Iterable[Any]) -> bytes:
    """Hasilkan CSV UTF-8 dengan BOM agar ramah Excel."""

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(EXPORT_COLUMNS)
    for raw in rows:
        row = _as_dict(raw)
        writer.writerow(
            [
                row.get("id", ""),
                _safe_text(row.get("transaction_date", "")),
                _safe_text(row.get("description", "")),
                TYPE_LABELS.get(str(row.get("transaction_type", "")), row.get("transaction_type", "")),
                _safe_text(row.get("category", "")),
                _safe_text(SOURCE_LABELS.get(
                    str(row.get("category_source", "")), row.get("category_source", "")
                )),
                f"{float(row.get('amount', 0.0)):.2f}",
                _safe_text(row.get("source_file") or ""),
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def filtered_frame(rows: Iterable[Any]) -> pd.DataFrame:
    records = [_as_dict(row) for row in rows]
    if not records:
        return pd.DataFrame(columns=EXPORT_COLUMNS)
    return pd.DataFrame(records)
